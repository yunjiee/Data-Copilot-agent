# mcp_servers/analytics_data_server/server.py

from typing import Any

from mcp.server.fastmcp import FastMCP

from .service import AnalyticsService

mcp = FastMCP(
    name="analytics-data-server",
    json_response=True,
)

service = AnalyticsService()


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
            回傳商品筆數，預設為 10，最多為 100。

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