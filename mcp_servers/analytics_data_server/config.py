from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 定義明確的路徑 mcp_servers/analytics_data_server/config.py 
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 專案根目錄下的 .env
ENV_PATH = PROJECT_ROOT / ".env"

# analytics_data_server 本身的目錄
ANALYTICS_SERVER_ROOT = Path(__file__).resolve().parent

# SQL 檔案所在目錄
SQL_DIR = ANALYTICS_SERVER_ROOT / "SQL"


class AnalyticsServerSettings(BaseSettings):
    """Analytics MCP Server 的環境設定。"""

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )
    # 建立 BigQuery Query Job，以及歸屬查詢費用的專案。
    bigquery_project: str = Field(
        validation_alias="BIGQUERY_PROJECT",
    )

    bigquery_data_project: str = Field(
        validation_alias="BIGQUERY_DATA_PROJECT",
    )

    bigquery_dataset: str = Field(
        validation_alias="BIGQUERY_DATASET",
    )

    bigquery_location: str = Field(
        default="US",
        validation_alias="BIGQUERY_LOCATION",
    )

    maximum_bytes_billed: int = Field(
        default=104857600,
        alias="MAXIMUM_BYTES_BILLED",
    )
    # 等待 BigQuery 查詢結果的最長秒數。
    query_timeout_seconds: int = Field(
        default=60,
        gt=0,
        validation_alias="BIGQUERY_QUERY_TIMEOUT_SECONDS",
    )

    @property
    def order_items_table(self) -> str:
        """取得 TheLook order_items 完整資料表名稱。"""

        return (
            f"{self.bigquery_data_project}."
            f"{self.bigquery_dataset}."
            "order_items"
        )

    @property
    def products_table(self) -> str:
        """取得 TheLook products 完整資料表名稱。"""

        return (
            f"{self.bigquery_data_project}."
            f"{self.bigquery_dataset}."
            "products"
        )

    @property
    def users_table(self) -> str:
        """取得 TheLook users 完整資料表名稱。"""

        return (
            f"{self.bigquery_data_project}."
            f"{self.bigquery_dataset}."
            "users"
        )


settings = AnalyticsServerSettings()