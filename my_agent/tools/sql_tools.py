from __future__ import annotations

import logging
import re
from typing import Any
from datetime import datetime

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery
from mcp_servers.analytics_data_server.config import settings
from ..config import config
from .cache_tools import save_cache_data

logger = logging.getLogger(__name__)

# --- 強制防護機制：記錄 SQL 驗證與修復失敗的次數 ---
_sql_fix_count = 0


def reset_sql_fix_state() -> str:
    """重設 SQL 語法驗證與自我修正的重試計數器狀態。"""
    global _sql_fix_count
    _sql_fix_count = 0
    return "✅ SQL 自我修正狀態與計數器已重設。"


def _record_fix_failure() -> int:
    """增加修正失敗計數並回傳目前累計次數。"""
    global _sql_fix_count
    _sql_fix_count += 1
    return _sql_fix_count


# 允許查詢的資料集前綴（預設為 bigquery-public-data.thelook_ecommerce.）
ALLOWED_TABLE_PREFIX = f"{settings.bigquery_data_project}.{settings.bigquery_dataset}.".lower()


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
    references = re.findall(r"\b(?:FROM|JOIN)\s+([`\w\-.*]+)", cleaned, flags=re.IGNORECASE)

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


# SQL 字串長度上限，避免超長輸入
MAX_SQL_LENGTH = 4000

# 單次查詢預估掃描量安全上限（100 MiB）
MAX_SCAN_BYTES_LIMIT = 100 * 1024 * 1024

def _validate_business_and_safety_rules(sql: str) -> dict[str, Any]:
    """檢查 SQL 是否符合安全與商業計算規範（防止除零錯誤、限制時間等）。"""
    normalized = sql.strip().upper()

    # 1. 安全防護：禁止任何非唯讀查詢 (DDL / DML)
    forbidden_keywords = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bUPDATE\b",
        r"\bINSERT\b",
        r"\bTRUNCATE\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bMERGE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bEXPORT\b",
        r"\bCALL\b",
        r"\bEXECUTE\b",
        r"\bLOAD\b",
        r"\bEXTERNAL_QUERY\b",
        r"\bINFORMATION_SCHEMA\b",
    ]
    for pattern in forbidden_keywords:
        if re.search(pattern, normalized):
            keyword = pattern.replace(r"\b", "")  # 先取出關鍵字，f-string 內不可含反斜線（Python 3.11 相容）
            return {
                "valid": False,
                "error_message": f"禁止執行非唯讀指令（包含關鍵字: {keyword}）。",
            }

    # 1-2. 只允許單一敘述，避免以分號夾帶第二個指令
    if ";" in sql.strip().rstrip(";"):
        return {"valid": False, "error_message": "只允許單一 SELECT 敘述，不可包含多個以分號分隔的指令。"}

    # 2. 資料範圍保護：只允許查詢 TheLook 資料集
    disallowed_tables = _find_disallowed_tables(sql)
    if disallowed_tables:
        return {
            "valid": False,
            "error_message": (
                f"只能查詢 {ALLOWED_TABLE_PREFIX}* 底下的資料表，"
                f"不允許存取：{', '.join(disallowed_tables)}。"
            ),
        }

    # 3. 商業計算規則：延續 calculation_tools 的除零保護
    # 如果使用裸除法 / 號且未搭配 SAFE_DIVIDE，提醒使用 SAFE_DIVIDE 避免除以零報錯
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


def check_sql_syntax(sql: str) -> dict[str, Any]:
    """檢查 BigQuery SQL 語法與執行 Dry Run 驗證。

    執行順序：
    1. 本地安全與計算規則檢驗（防 DML、強制 SAFE_DIVIDE 防除零等）。
    2. 透過 BigQuery dry_run 參數試運行 SQL 語句，驗證語法與欄位正確性，
       不產生實際資料查詢成本與掃描費用。

    Args:
        sql: 欲驗證的 SQL 查詢字串。

    Returns:
        包含 valid (bool)、預估處理位元組數或詳細錯誤建議的字典。
    """
    max_retries = config.max_sql_fix_iterations

    # 系統強制攔截：已達修正上限時直接鎖定，杜絕模型持續空轉重試
    if _sql_fix_count >= max_retries:
        return {
            "status": "error",
            "valid": False,
            "retry_limit_exceeded": True,
            "error_message": f"🛑 [系統強制攔截] 已達 SQL 自我修正次數上限 ({max_retries} 次)。系統已鎖定驗證權限。",
            "suggestion": "請立即停止修正 SQL，並直接向使用者說明查詢失敗原因與遭遇的錯誤。",
        }

    if not sql or not sql.strip():
        fail_count = _record_fix_failure()
        return {
            "status": "error",
            "valid": False,
            "error_message": "SQL 語句不可為空。",
            "attempts": fail_count,
        }

    if len(sql) > MAX_SQL_LENGTH:
        return {
            "status": "error",
            "valid": False,
            "error_message": f"SQL 長度超過上限 ({MAX_SQL_LENGTH} 字元)。",
        }

    # 第一階段：規則與除零防護驗證
    rule_check = _validate_business_and_safety_rules(sql)
    if not rule_check["valid"]:
        fail_count = _record_fix_failure()
        return {
            "status": "error",
            "valid": False,
            "error_message": f"業務與安全規則檢驗失敗：{rule_check['error_message']}",
            "retry_limit_exceeded": fail_count >= max_retries,
            "attempts": fail_count,
            "suggestion": (
                "已達修正次數上限，請停止修復並回報使用者。"
                if fail_count >= max_retries
                else "請參考錯誤訊息修正 SQL 運算邏輯後重新檢查。"
            ),
        }

    # 第二階段：BigQuery Dry Run 語法檢查
    if not settings.bigquery_project:
        fail_count = _record_fix_failure()
        return {
            "status": "error",
            "valid": False,
            "error_message": "尚未設定 BigQuery 專案 ID。",
            "attempts": fail_count,
        }

    client = bigquery.Client(
        project=settings.bigquery_project,
        location=settings.bigquery_location,
    )
    job_config = bigquery.QueryJobConfig(dry_run=True)

    try:
        query_job = client.query(sql, job_config=job_config)

        # 最終防線：以 BigQuery 實際解析出的被讀取資料表比對白名單
        disallowed_refs = _find_disallowed_referenced_tables(query_job.referenced_tables)
        if disallowed_refs:
            return {
                "status": "error",
                "valid": False,
                "error_message": (
                    f"只能查詢 {ALLOWED_TABLE_PREFIX}* 底下的資料表，"
                    f"不允許存取：{', '.join(disallowed_refs)}。"
                ),
            }

        total_bytes = query_job.total_bytes_processed or 0
        mib_processed = round(total_bytes / (1024**2), 2)

        # Python 硬性防護：超過 100 MiB 掃描量直接判定不通過
        if total_bytes > MAX_SCAN_BYTES_LIMIT:
            return {
                "status": "error",
                "valid": False,
                "error_message": f"預估掃描量達 {mib_processed} MiB，超過系統安全上限 (100 MiB)！",
                "estimated_mib_processed": mib_processed,
                "suggestion": "請在 WHERE 條件中加強時間過濾，或限制查詢欄位以降低掃描成本。",
            }

        return {
            "status": "success",
            "valid": True,
            "estimated_bytes_processed": total_bytes,
            "estimated_mib_processed": round(total_bytes / (1024**2), 2),
            "message": "SQL 語法正確，Dry Run 驗證通過。",
        }
    except GoogleAPICallError as e:
        error_detail = e.message if hasattr(e, "message") else str(e)
        logger.warning("SQL Dry Run 失敗: %s", error_detail)
        return {
            "status": "error",
            "valid": False,
            "error_message": f"BigQuery 語法或欄位錯誤: {error_detail}",
            "suggestion": "請仔細對照 TheLook 資料集綱要（Schema），反思並修正 SQL 後重新驗證。",
        }
    except Exception as e:
        return {
            "status": "error",
            "valid": False,
            "error_message": f"未預期錯誤: {str(e)}",
        }


def execute_sql_query(sql: str) -> dict[str, Any]:
    """在 BigQuery 執行已通過驗證的 SQL 查詢並取得結果。

    底層防護：內部會強制調用 check_sql_syntax。只有在驗證狀態為 success 且
    valid 為 True 時，Python 才會放行並實際送出 BigQuery 查詢。

    Args:
        sql: 欲執行的標準 SQL 語句。

    Returns:
        包含查詢結果列表與欄位資訊的字典。
    """
    # 核心硬性防護：透過 Python 強制執行語法與 Dry Run 檢查
    check_result = check_sql_syntax(sql)
    if check_result.get("status") != "success" or not check_result.get("valid"):
        return {
            "status": "error",
            "error_message": f"安全與語法審查未通過，Python 底層拒絕執行查詢！原因：{check_result.get('error_message')}",
            "suggestion": check_result.get("suggestion", "請重新檢查並修正 SQL 語法與規則後再試。"),
        }

    client = bigquery.Client(
        project=settings.bigquery_project,
        location=settings.bigquery_location,
    )

    try:
        query_job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                maximum_bytes_billed=settings.maximum_bytes_billed,
            ),
        )
        results = query_job.result()
        rows = [dict(row.items()) for row in results]

        # 轉換不可 JSON 序列化的日期/時間格式
        for row in rows:
            for k, v in row.items():
                if isinstance(v, (datetime,)):
                    row[k] = v.isoformat()

        # Python 硬性控制：查詢成功自動儲存快取，杜絕模型忘記存檔
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cache_filename = f"bq_query_{timestamp}.json"
        cache_path = save_cache_data(
            category="analytics",
            filename=cache_filename,
            data=rows,
        )

        # 查詢執行成功，重置自我修正計數器
        reset_sql_fix_state()

        return {
            "status": "success",
            "row_count": len(rows),
            "cache_saved": True,
            "cache_path": cache_path,
            "data": rows,
        }
    except GoogleAPICallError as e:
        error_detail = e.message if hasattr(e, "message") else str(e)
        logger.warning("SQL Dry Run 失敗: %s", e)
        return {
            "status": "error",
            "error_message": f"執行時期錯誤: {error_detail}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
        }