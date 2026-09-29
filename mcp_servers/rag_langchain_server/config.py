"""mcp_servers/rag_langchain_server/config.py

LangChain 版 RAG Server 的設定。

與原版 rag_server 的差異：
- 使用獨立的 Collection 名稱與 Qdrant 資料夾，避免 Qdrant Local Mode
  同一路徑只能被一個程序開啟的鎖定衝突，也讓兩版可以並存比較。
- Embedding 模型、chunk_size、chunk_overlap 預設與原版相同，
  讓兩版比較時唯一的差異是「切塊與檢索的實作方式」。
"""

from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LangChainRagSettings(BaseSettings):
    """LangChain 版 RAG Server 設定（環境變數前綴 LC_RAG_）。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 與原版共用同一個 Embedding 模型設定（RAG_EMBEDDING_MODEL），確保比較公平
    embedding_model: str = Field(
        default="intfloat/multilingual-e5-small",
        validation_alias=AliasChoices(
            "LC_RAG_EMBEDDING_MODEL",
            "RAG_EMBEDDING_MODEL",
        ),
    )

    collection_name: str = Field(
        default="ecommerce_kb_langchain",
        validation_alias="LC_RAG_COLLECTION_NAME",
    )

    source_dir_setting: Path = Field(
        default=Path("data/knowledge_base"),
        validation_alias="LC_RAG_SOURCE_DIR",
    )

    # 與原版的 data/qdrant 分開
    qdrant_path_setting: Path = Field(
        default=Path("data/qdrant_langchain"),
        validation_alias="LC_RAG_QDRANT_PATH",
    )

    chunk_size: int = Field(
        default=500,
        gt=0,
        validation_alias="LC_RAG_CHUNK_SIZE",
    )

    chunk_overlap: int = Field(
        default=100,
        ge=0,
        validation_alias="LC_RAG_CHUNK_OVERLAP",
    )

    embedding_batch_size: int = Field(
        default=16,
        gt=0,
        validation_alias="LC_RAG_EMBEDDING_BATCH_SIZE",
    )

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "LangChainRagSettings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("LC_RAG_CHUNK_OVERLAP 必須小於 LC_RAG_CHUNK_SIZE")
        return self

    @property
    def source_dir(self) -> Path:
        """原始知識文件的完整路徑。"""
        if self.source_dir_setting.is_absolute():
            return self.source_dir_setting
        return PROJECT_ROOT / self.source_dir_setting

    @property
    def qdrant_path(self) -> Path:
        """LangChain 版 Qdrant 本機資料庫的完整路徑。"""
        if self.qdrant_path_setting.is_absolute():
            return self.qdrant_path_setting
        return PROJECT_ROOT / self.qdrant_path_setting


lc_rag_settings = LangChainRagSettings()
rag_settings = lc_rag_settings  # 向下相容別名
