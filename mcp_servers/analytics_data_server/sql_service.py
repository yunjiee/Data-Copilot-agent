# mcp_servers/analytics_data_server/sql_service.py
"""Text-to-SQL 的驗證與執行：安全規則、Dry Run、重試上限、實際執行與快取。

原本位於 my_agent/tools/sql_tools.py，現在全部由 MCP Server 負責，
Agent 端只剩下呼叫 MCP Tool。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery

from .config import settings

logger = logging.getLogger(__name__)

# 允許查詢的資料集前綴（預設為 bigquery-public-data.thelook_ecommerce.）
# 顯示用（保留原始大小寫；BigQuery 資料集與資料表名稱區分大小寫，訊息若轉小寫會誤導模型）
DISPLAY_TABLE_PREFIX = (
    f"{settings.bigquery_data_project}.{settings.bigquery_dataset}."
)
# 比對用（全小寫）
ALLOWED_TABLE_PREFIX = DISPLAY_TABLE_PREFIX.lower()

# SQL 字串長度上限，避免超長輸入
MAX_SQL_LENGTH = 4000

# 單次查詢預估掃描量安全上限（100 MiB）
MAX_SCAN_BYTES_LIMIT = 100 * 1024 * 1024

_FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE",
    "MERGE", "GRANT", "REVOKE", "EXPORT", "CALL", "EXECUTE", "LOAD",
    "EXTERNAL_QUERY", "INFORMATION_SCHEMA",
]


def _find_disallowed_tables(sql: str) -> list[str]:
    """找出 FROM / JOIN 後面不屬於允許資料集的資料表。

    規則：
    - 含「.」的資料表參照，必須以 ALLOWED_TABLE_PREFIX 開頭（完整的 專案.資料集.資料表）。
      兩段式的「資料集.資料表」會落在計費專案，同樣拒絕。
    - 不含「.」的名稱（例如 WITH 定義的 CTE、UNNEST）略過；
      BigQuery Client 未設定預設資料集，未完整指定的真實資料表在 Dry Run 就會失敗。
    - 先移除 EXTRACT(... FROM 欄位)，避免把欄位誤判成資料表。
    """
    cleaned = re.sub(r"EXTRACT\s*\([^()]*\)", " ", sql, flags=re.IGNORECASE)
    references = re.findall(
        r"\b(?:FROM|JOIN)\s+([`\w\-.*]+)", cleaned, flags=re.IGNORECASE
    )

    disallowed: list[str] = []
    for ref in references:
        table = ref.replace("`", "").lower()
        if "." in table and not table.startswith(ALLOWED_TABLE_PREFIX):
            disallowed.append(ref.replace("`", ""))
    return disallowed


def _find_disallowed_referenced_tables(referenced_tables: Any) -> list[str]:
    """用 BigQuery dry-run 回報的「實際被讀取資料表」做最終比對，不依賴正則解析。"""
    disallowed: list[str] = []
    for table in referenced_tables or []:
        full_name = f"{table.project}.{table.dataset_id}.{table.table_id}"
        if not full_name.lower().startswith(ALLOWED_TABLE_PREFIX):
            disallowed.append(full_name)
    return disallowed


def _validate_business_and_safety_rules(sql: str) -> dict[str, Any]:
    """檢查 SQL 是否符合安全與商業計算規範（唯讀、資料範圍、除零、掃描範圍）。"""
    normalized = sql.strip().upper()

    # 1. 安全防護：禁止任何非唯讀查詢 (DDL / DML)
    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized):
            return {
                "valid": False,
                "error_message": f"禁止執行非唯讀指令（包含關鍵字: {keyword}）。",
            }

    # 1-2. 只允許單一敘述，避免以分號夾帶第二個指令
    if ";" in sql.strip().rstrip(";"):
        return {
            "valid": False,
            "error_message": "只允許單一 SELECT 敘述，不可包含多個以分號分隔的指令。",
        }

    # 2. 資料範圍保護：只允許查詢 TheLook 資料集
    disallowed_tables = _find_disallowed_tables(sql)
    if disallowed_tables:
        return {
            "valid": False,
            "error_message": (
                f"只能查詢 {DISPLAY_TABLE_PREFIX}* 底下的資料表，"
                f"不允許存取：{', '.join(disallowed_tables)}。"
            ),
        }

    # 3. 商業計算規則：裸除法必須改用 SAFE_DIVIDE，避免分母為 0 造成查詢崩潰
    if "/" in sql and "SAFE_DIVIDE" not in normalized:
        return {
            "valid": False,
            "error_message": (
                "檢測到除法運算。為避免前期數值或分母為 0 造成查詢崩潰，"
                "請將 a / b 改用 BigQuery 標準語法 SAFE_DIVIDE(a, b)。"
            ),
        }

    # 4. 查詢範圍保護：確認是否有過大掃描風險
    if "WHERE" not in normalized and "LIMIT" not in normalized:
        return {
            "valid": False,
            "error_message": "SQL 查詢缺少 WHERE 條件過濾或 LIMIT 限制，可能會掃描過多數據。",
        }

    return {"valid": True}


def _json_safe(value: Any) -> Any:
    """把 BigQuery 回傳的型別轉成可 JSON 序列化的值。"""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


class SqlService:
    """Text-to-SQL 的驗證（規則 + Dry Run）與執行服務。"""

    MAX_SCAN_MIB = MAX_SCAN_BYTES_LIMIT // (1024 * 1024)

    def __init__(self) -> None:
        self.client = bigquery.Client(
            project=settings.bigquery_project,
            location=settings.bigquery_location,
        )
        # 驗證失敗計數：達上限後鎖定驗證，避免模型無限重試；成功執行後重設。
        self._fix_count = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 重試計數
    # ------------------------------------------------------------------
    def reset_fix_state(self) -> dict[str, Any]:
        """重設 SQL 自我修正計數器。"""
        with self._lock:
            self._fix_count = 0
        return {
            "status": "success",
            "message": "SQL 自我修正狀態與計數器已重設。",
        }

    def _current_fix_count(self) -> int:
        with self._lock:
            return self._fix_count

    def _record_fix_failure(self) -> int:
        with self._lock:
            self._fix_count += 1
            return self._fix_count

    # ------------------------------------------------------------------
    # 驗證
    # ------------------------------------------------------------------
    def check_sql_syntax(
        self,
        sql: str,
        query_parameters: list[Any] | None = None,
        track_failures: bool = True,
    ) -> dict[str, Any]:
        """先跑本地安全規則，再用 BigQuery Dry Run 驗證語法與欄位。

        Args:
            sql: 欲驗證的 SQL。
            query_parameters: SQL 中 @參數 對應的 BigQuery Query Parameter（Dry Run 需要）。
            track_failures: 是否把失敗計入模型自我修正次數。
                封裝工具（get_daily_sales 等）使用固定 SQL 範本，失敗不是模型造成的，
                傳 False 以免誤鎖模型的 check_sql_syntax 權限。
        """
        max_retries = settings.max_sql_fix_iterations

        def record_failure() -> tuple[int, bool]:
            if not track_failures:
                return 0, False
            count = self._record_fix_failure()
            return count, count >= max_retries

        # 已達修正上限時直接鎖定，杜絕模型持續空轉重試
        if track_failures and self._current_fix_count() >= max_retries:
            return {
                "status": "error",
                "valid": False,
                "retry_limit_exceeded": True,
                "error_message": (
                    f"🛑 [系統強制攔截] 已達 SQL 自我修正次數上限 ({max_retries} 次)。"
                    "系統已鎖定驗證權限。"
                ),
                "suggestion": "請立即停止修正 SQL，並直接向使用者說明查詢失敗原因與遭遇的錯誤。",
            }

        if not sql or not sql.strip():
            return self._fail("SQL 語句不可為空。", track_failures)

        if len(sql) > MAX_SQL_LENGTH:
            return {
                "status": "error",
                "valid": False,
                "error_message": f"SQL 長度超過上限 ({MAX_SQL_LENGTH} 字元)。",
            }

        # 第一階段：規則與除零防護驗證
        rule_check = _validate_business_and_safety_rules(sql)
        if not rule_check["valid"]:
            fail_count, exceeded = record_failure()
            return {
                "status": "error",
                "valid": False,
                "error_message": f"業務與安全規則檢驗失敗：{rule_check['error_message']}",
                "retry_limit_exceeded": exceeded,
                "attempts": fail_count,
                "suggestion": (
                    "已達修正次數上限，請停止修復並回報使用者。"
                    if exceeded
                    else "請參考錯誤訊息修正 SQL 運算邏輯後重新檢查。"
                ),
            }

        # 第二階段：BigQuery Dry Run
        try:
            query_job = self.client.query(
                sql,
                job_config=bigquery.QueryJobConfig(
                    dry_run=True,
                    query_parameters=query_parameters or [],
                ),
                location=settings.bigquery_location,
            )

            # 最終防線：以 BigQuery 實際解析出的被讀取資料表比對白名單
            disallowed_refs = _find_disallowed_referenced_tables(
                query_job.referenced_tables
            )
            if disallowed_refs:
                return {
                    "status": "error",
                    "valid": False,
                    "error_message": (
                        f"只能查詢 {DISPLAY_TABLE_PREFIX}* 底下的資料表，"
                        f"不允許存取：{', '.join(disallowed_refs)}。"
                    ),
                }

            total_bytes = query_job.total_bytes_processed or 0
            mib_processed = round(total_bytes / (1024**2), 2)

            if total_bytes > MAX_SCAN_BYTES_LIMIT:
                return {
                    "status": "error",
                    "valid": False,
                    "error_message": (
                        f"預估掃描量達 {mib_processed} MiB，超過系統安全上限 (100 MiB)！"
                    ),
                    "estimated_mib_processed": mib_processed,
                    "suggestion": "請在 WHERE 條件中加強時間過濾，或限制查詢欄位以降低掃描成本。",
                }

            return {
                "status": "success",
                "valid": True,
                "estimated_bytes_processed": total_bytes,
                "estimated_mib_processed": mib_processed,
                "message": "SQL 語法正確，Dry Run 驗證通過。",
            }
        except GoogleAPICallError as error:
            error_detail = getattr(error, "message", None) or str(error)
            logger.warning("SQL Dry Run 失敗: %s", error_detail)
            fail_count, exceeded = record_failure()
            return {
                "status": "error",
                "valid": False,
                "error_message": f"BigQuery 語法或欄位錯誤: {error_detail}",
                "retry_limit_exceeded": exceeded,
                "attempts": fail_count,
                "suggestion": (
                    "已達修正次數上限，請停止修復並回報使用者。"
                    if exceeded
                    else "請仔細對照 TheLook 資料集綱要（Schema），反思並修正 SQL 後重新驗證。"
                ),
            }
        except Exception as error:  # noqa: BLE001
            logger.exception("SQL Dry Run 發生未預期錯誤")
            return {
                "status": "error",
                "valid": False,
                "error_message": f"未預期錯誤: {error}",
            }

    def _fail(self, message: str, track_failures: bool = True) -> dict[str, Any]:
        fail_count = self._record_fix_failure() if track_failures else 0
        return {
            "status": "error",
            "valid": False,
            "error_message": message,
            "attempts": fail_count,
        }

    # ------------------------------------------------------------------
    # 執行
    # ------------------------------------------------------------------
    def execute_sql_query(self, sql: str) -> dict[str, Any]:
        """強制先驗證（規則 + Dry Run），通過後才實際送出查詢並寫入快取。"""
        check_result = self.check_sql_syntax(sql)
        if check_result.get("status") != "success" or not check_result.get("valid"):
            return {
                "status": "error",
                "error_message": (
                    "安全與語法審查未通過，MCP Server 拒絕執行查詢！"
                    f"原因：{check_result.get('error_message')}"
                ),
                "retry_limit_exceeded": check_result.get("retry_limit_exceeded", False),
                "suggestion": check_result.get(
                    "suggestion", "請重新檢查並修正 SQL 語法與規則後再試。"
                ),
            }

        try:
            query_job = self.client.query(
                sql,
                job_config=bigquery.QueryJobConfig(
                    maximum_bytes_billed=settings.maximum_bytes_billed,
                ),
                location=settings.bigquery_location,
            )
            results = query_job.result(timeout=settings.query_timeout_seconds)
            rows = [_json_safe(dict(row.items())) for row in results]
        except GoogleAPICallError as error:
            error_detail = getattr(error, "message", None) or str(error)
            logger.warning("SQL 執行失敗: %s", error_detail)
            return {"status": "error", "error_message": f"執行時期錯誤: {error_detail}"}
        except Exception as error:  # noqa: BLE001
            logger.exception("SQL 執行發生未預期錯誤")
            return {"status": "error", "error_message": str(error)}

        # 查詢成功：自動儲存快取，杜絕模型忘記存檔；並重設修正計數器
        cache_path = self.save_analytics_cache(rows)
        self.reset_fix_state()

        return {
            "status": "success",
            "row_count": len(rows),
            "cache_saved": True,
            "cache_path": cache_path,
            "data": rows,
        }

    @staticmethod
    def save_analytics_cache(rows: Any, query_name: str = "query") -> str:
        """以與 my_agent 快取工具相同的格式寫入 cache/analytics，report_agent 才讀得到。"""
        target_dir = settings.cache_root / "cache" / "analytics"
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"bq_{query_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        target_path = target_dir / filename
        payload = {
            "saved_at": datetime.now().isoformat(),
            "category": "analytics",
            "filename": filename,
            "data": rows,
        }
        with open(target_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
        return str(target_path.resolve())
