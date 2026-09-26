# mcp_servers/analytics_data_server/service.py

from __future__ import annotations

import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import date
from typing import Any

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery

from .config import SQL_DIR, settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """負責與 BigQuery 溝通的應用服務。"""

    def __init__(self) -> None:
        self.client = bigquery.Client(
            project=settings.bigquery_project,
            location=settings.bigquery_location,
        )
        self.order_items_table = settings.order_items_table
        self.products_table = settings.products_table

    def get_daily_sales(
        self,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """
        取得指定日期區間的每日訂單數、銷售件數與銷售金額。
        """
        
        # 1. 接收 MCP Tool 傳進來的參數
        parsed_start_date, parsed_end_date = (
            self._parse_date_range(
                start_date=start_date,
                end_date=end_date,
            )
        )
        # 2. 載入商品績效 SQL
        sql_template = self._load_sql(
            filename="daily_sales.sql",
        )

        # 只有資料表名稱使用 format 插入。
        # 使用者提供的日期仍然使用 BigQuery Query Parameter，
        # 避免 SQL Injection。
        sql = sql_template.format(
            table_name=self.order_items_table,
        )

        # 日期仍使用 BigQuery Query Parameter
        query_parameters = [
            bigquery.ScalarQueryParameter(
                "start_date",
                "DATE",
                parsed_start_date,
            ),
            bigquery.ScalarQueryParameter(
                "end_date",
                "DATE",
                parsed_end_date,
            ),
        ]

        # 3. 執行 BigQuery
        rows, query_job = self._execute_query(
            query_name="daily_sales",
            sql=sql,
            query_parameters=query_parameters,
        )

        # 4. 整理資料格式
        data = [
            {
                "order_date": row["order_date"].isoformat(),
                "order_count": int(
                    dict(row).get("order_count") or 0
                ),
                "units_sold": int(
                    dict(row).get("units_sold") or 0
                ),
                "revenue": float(
                    dict(row).get("revenue") or 0
                ),
            }
            for row in rows
        ]

        # 5. 建立統一回傳格式
        return self._build_response(
            query_type="daily_sales",
            filters={
                "start_date": parsed_start_date.isoformat(),
                "end_date": parsed_end_date.isoformat(),
            },
            data=data,
            query_job=query_job,
        )
    

    def get_product_performance(
        self,
        start_date: str,
        end_date: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        取得指定日期區間內，依營收由高至低排列的商品績效。

        包含：
        - 商品名稱
        - 商品分類
        - 商品品牌
        - 訂單數
        - 銷售件數
        - 銷售金額
        - 退貨件數
        - 退貨率
        """
        # 1. 驗證並轉換日期
        parsed_start_date, parsed_end_date = (
            self._parse_date_range(
                start_date=start_date,
                end_date=end_date,
            )
        )

        # 2. 驗證回傳筆數
        parsed_limit = self._validate_limit(
            limit=limit,
        )

        # 3. 載入商品績效 SQL
        sql_template = self._load_sql(
            filename="product_performance.sql",
        )

        sql = sql_template.format(
            order_items_table=self.order_items_table,
            products_table=self.products_table,
        )

        query_parameters = [
            bigquery.ScalarQueryParameter(
                "start_date",
                "DATE",
                parsed_start_date,
            ),
            bigquery.ScalarQueryParameter(
                "end_date",
                "DATE",
                parsed_end_date,
            ),
            bigquery.ScalarQueryParameter(
                "limit",
                "INT64",
                parsed_limit,
            ),
        ]

        # 4. 執行 BigQuery
        rows, query_job = self._execute_query(
            query_name="product_performance",
            sql=sql,
            query_parameters=query_parameters,
        )

        # 5. 整理資料格式
        data = [
            {
                "product_id": int(
                    row["product_id"]
                ),
                "product_name": row["product_name"],
                "category": row["category"],
                "brand": row["brand"],
                "order_count": int(
                    row["order_count"] or 0
                ),
                "units_sold": int(
                    row["units_sold"] or 0
                ),
                "revenue": float(
                    row["revenue"] or 0
                ),
                "return_count": int(
                    row["return_count"] or 0
                ),
                "return_rate": float(
                    row["return_rate"] or 0
                ),
            }
            for row in rows
        ]

        # 6. 建立統一回傳格式
        return self._build_response(
            query_type="product_performance",
            filters={
                "start_date": parsed_start_date.isoformat(),
                "end_date": parsed_end_date.isoformat(),
                "limit": parsed_limit,
                "sort_by": "revenue",
                "sort_order": "desc",
            },
            data=data,
            query_job=query_job,
        )

    def _execute_query(
        self,
        query_name: str,
        sql: str,
        query_parameters: list[
            bigquery.ScalarQueryParameter
        ],
    ) -> tuple[list[Any], Any]:

        """執行 BigQuery 查詢並回傳資料列與 Query Job。"""
        job_config = bigquery.QueryJobConfig(
            query_parameters=query_parameters or [],
            maximum_bytes_billed=(
                settings.maximum_bytes_billed
            ),
            use_query_cache=True,
        )

        logger.info(
            "準備執行 BigQuery 查詢：query_name=%s, billing_project=%s, location=%s",
            query_name,
            settings.bigquery_project,
            settings.bigquery_location,
        )

        try:
            query_job = self.client.query(
                query=sql,
                job_config=job_config,
                location=settings.bigquery_location,
            )

            rows = list(
                query_job.result(
                    timeout=settings.query_timeout_seconds,
                )
            )
        except FuturesTimeoutError as error:
            logger.exception(
                "BigQuery 查詢逾時：query_name=%s",
                query_name,
            )
            raise RuntimeError(
                f"BigQuery 查詢逾時：{query_name}"
            ) from error

        except GoogleAPICallError as error:
            logger.exception(
                "BigQuery 查詢失敗：query_name=%s",
                query_name,
            )
            raise RuntimeError(
                f"BigQuery 查詢失敗：{query_name}；{error}"
            ) from error
        
        logger.info(
                "BigQuery 查詢完成："
                "query_name=%s, job_id=%s, row_count=%s",
                query_name,
                query_job.job_id,
                len(rows),
            )

        return rows, query_job
    
    def _build_response(
        self,
        query_type: str,
        filters: dict[str, Any],
        data: list[dict[str, Any]],
        query_job: Any,
    ) -> dict[str, Any]:
        """
        建立共用的回傳格式。
        """

        processed_bytes = int(
            query_job.total_bytes_processed or 0
        )

        billed_bytes = int(
            query_job.total_bytes_billed or 0
        )

        query_metadata: dict[str, Any] = {
            "job_id": query_job.job_id,
            "cache_hit": bool(query_job.cache_hit),
            "processed_bytes": processed_bytes,
            "processed_mib": round(
                processed_bytes / (1024**2),
                4,
            ),
            "billed_bytes": billed_bytes,
            "billed_mib": round(
                billed_bytes / (1024**2),
                4,
            ),
        }

        # BigQuery 價格可能調整，不建議直接寫死在 service.py。
        # 如果 config.py 有設定價格，才計算估計費用。
        price_per_tib_usd = getattr(
            settings,
            "bigquery_price_per_tib_usd",
            None,
        )

        if price_per_tib_usd is not None:
            estimated_cost_usd = (
                billed_bytes
                / (1024**4)
                * price_per_tib_usd
            )

            query_metadata[
                "estimated_on_demand_cost_usd"
            ] = round(
                estimated_cost_usd,
                8,
            )

        return {
            "status": "success",
            "query_type": query_type,
            "filters": filters,
            "row_count": len(data),
            "data": data,
            "query_metadata": query_metadata,
        }
    
    @staticmethod  # 這個方法雖然放在類別裡，但它不需要使用物件本身的資料，也不需要使用類別本身的資料。
    def _parse_date_range(
        start_date: str,
        end_date: str,
    ) -> tuple[date, date]:
        """
        驗證開始日期與結束日期。
        """

        parsed_start_date = (
            AnalyticsService._parse_date(
                value=start_date,
                field_name="start_date",
            )
        )

        parsed_end_date = (
            AnalyticsService._parse_date(
                value=end_date,
                field_name="end_date",
            )
        )

        if parsed_start_date > parsed_end_date:
            raise ValueError(
                "start_date 不可以晚於 end_date。"
            )
            
        day_diff = (parsed_end_date - parsed_start_date).days
        if day_diff > 7:
            raise ValueError(
                f"查詢區間為 {day_diff} 天，已超過安全規範上限 7 天！"
                f"請將查詢期間縮小至 7 天以內（例如：{parsed_start_date} 至 {parsed_start_date.replace(day=min(parsed_start_date.day + 6, 28))}）。"
            )

        return (
            parsed_start_date,
            parsed_end_date,
        )

    @staticmethod
    def _parse_date(
        value: str,
        field_name: str,
    ) -> date:
        """
        將 YYYY-MM-DD 字串轉成 date。
        """

        try:
            return date.fromisoformat(
                value
            )

        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{field_name} 必須使用 YYYY-MM-DD 格式。"
            ) from error

    @staticmethod
    def _validate_limit(
        limit: int,
    ) -> int:
        """
        驗證商品查詢的回傳筆數。

        最少 1 筆，最多 100 筆。
        """

        # bool 是 int 的子類別，所以要先排除 True、False
        if isinstance(limit, bool):
            raise ValueError(
                "limit 必須是整數。"
            )

        try:
            parsed_limit = int(limit)

        except (TypeError, ValueError) as error:
            raise ValueError(
                "limit 必須是整數。"
            ) from error

        if parsed_limit < 1:
            raise ValueError(
                "limit 不可以小於 1。"
            )

        if parsed_limit > 20:
            raise ValueError(
                "limit 不可以大於 20。"
            )

        return parsed_limit

    @staticmethod
    def _load_sql(
        filename: str,
    ) -> str:
        """從 Analytics Server 的 SQL 目錄讀取 SQL 檔案。"""

        sql_path = SQL_DIR / filename

        if not sql_path.exists():
            raise FileNotFoundError(
                f"找不到 SQL 檔案：{sql_path}"
            )
        
        if not sql_path.is_file():
            raise ValueError(
                f"指定的 SQL 路徑不是檔案：{sql_path}"
            )

        return sql_path.read_text(
            encoding="utf-8",
        )