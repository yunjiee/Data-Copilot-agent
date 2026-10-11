# MCP Inspector 測試： uv run mcp dev mcp_servers/analytics_data_server/server.py --with-editable .
# --with-editable = 把某個本地 Python 專案以 editable install 的方式加入執行環境

from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp_servers.analytics_data_server.service import AnalyticsService
from mcp_servers.analytics_data_server.sql_service import SqlService

mcp = FastMCP(
    name="analytics-data-server",
    json_response=True,
)

sql_service = SqlService()
service = AnalyticsService(sql_service)


@mcp.tool()
def check_sql_syntax(sql: str) -> dict[str, Any]:
    """
    檢查 BigQuery SQL 的安全規則並執行 Dry Run 驗證（不產生查詢費用）。

    檢查順序：
    1. 安全與商業規則：僅允許單一唯讀 SELECT、限定 TheLook 資料集、
       除法須使用 SAFE_DIVIDE、須有 WHERE 或 LIMIT。
    2. BigQuery Dry Run：驗證語法、欄位，並估算掃描量（上限 100 MiB）。

    驗證失敗會累計次數；達上限後回傳 retry_limit_exceeded=true，
    此時必須停止修正並向使用者回報。

    Args:
        sql: 欲驗證的 BigQuery Standard SQL。

    Returns:
        valid、預估掃描量，或 error_message 與 suggestion。
    """
    return sql_service.check_sql_syntax(sql=sql)


@mcp.tool()
def execute_sql_query(sql: str) -> dict[str, Any]:
    """
    執行 BigQuery SQL 查詢並取得結果。

    內部會強制重跑 check_sql_syntax（規則 + Dry Run），未通過則拒絕執行。
    執行成功後結果會自動存入 analytics 快取，不需再另行存檔。

    Args:
        sql: 欲執行的 BigQuery Standard SQL。

    Returns:
        row_count、cache_path 與查詢結果 data。
    """
    return sql_service.execute_sql_query(sql=sql)


@mcp.tool()
def reset_sql_fix_state() -> dict[str, Any]:
    """
    重設 SQL 驗證失敗的重試計數器。

    僅供系統內部使用：agent 端在每輪對話開始時由程式呼叫，不提供給模型。
    """
    return sql_service.reset_fix_state()


@mcp.tool()
def get_query_context() -> dict[str, Any]:
    """
    取得目前可查詢的資料表完整名稱、欄位綱要與查詢限制
    （日期跨度上限、商品筆數上限、掃描量上限、SQL 修正次數上限）。

    自行撰寫 SQL 之前必須先呼叫一次，並以回傳的資料表名稱與欄位撰寫 SQL。
    """
    return service.get_query_context()


@mcp.tool()
def get_daily_sales(
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """
    查詢 TheLook eCommerce 的每日銷售績效。

    Args:
        start_date:
            查詢開始日期，格式必須為 YYYY-MM-DD。

        end_date:
            查詢結束日期，格式必須為 YYYY-MM-DD。

    Returns:
        每日訂單數與銷售金額。
    """

    return service.get_daily_sales(
        start_date=start_date,
        end_date=end_date,
    )

@mcp.tool()
def get_product_performance(
    start_date: str,
    end_date: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    查詢指定日期區間內的商品銷售績效。

    適合回答：
    - 營收最高的商品
    - 熱銷商品排行
    - 商品銷售件數
    - 商品訂單數
    - 商品退貨率
    - Top N 商品

    Args:
        start_date:
            查詢開始日期，格式為 YYYY-MM-DD。
        end_date:
            查詢結束日期，格式為 YYYY-MM-DD。
        limit:
            回傳商品筆數，預設為 10；上限由系統設定決定（見 get_query_context 的 max_product_limit），超過會回傳錯誤。

    Returns:
        依營收由高至低排列的商品績效資料。
    """ 
    return service.get_product_performance(
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@mcp.tool()
def get_server_status() -> dict[str, str]:
    """
    檢查 Analytics MCP Server 是否正常運作。
    """

    return {
        "status": "ok",
        "server": "analytics-data-server",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")