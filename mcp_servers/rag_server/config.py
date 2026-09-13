from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RagSettings(BaseSettings):
    """Local RAG Server 設定。"""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    rag_embedding_model: str = Field(
        default="intfloat/multilingual-e5-small",
    )

    #  決定使用的版本
    rag_collection_name: str = Field(
        default="ecommerce_internal_knowledge",
    )

    rag_source_dir: Path = Field(
        default=Path("data/knowledge_base"),
    )

    rag_qdrant_path: Path = Field(
        default=Path("data/qdrant"),
    )

    rag_chunk_size: int = Field(
        default=500,
        gt=0,
    )

    # 下一個片段會和前一個片段重疊 ex.切割Chunk 1：第   0 ～ 499 字、Chunk 2：第 400 ～ 899 字
    rag_chunk_overlap: int = Field(
        default=100,
        ge=0,
    )

    rag_top_k: int = Field(
        default=5,
        gt=0,
        le=20,
    )

    rag_embedding_batch_size: int = Field(
        default=16,
        gt=0,
    )

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "RagSettings":
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError(
                "RAG_CHUNK_OVERLAP 必須小於 RAG_CHUNK_SIZE"
            )

        return self

    @property
    def source_dir(self) -> Path:
        """取得原始知識文件的完整路徑。"""
        if self.rag_source_dir.is_absolute():
            return self.rag_source_dir

        return PROJECT_ROOT / self.rag_source_dir

    @property
    def qdrant_path(self) -> Path:
        """取得 Qdrant 本機資料庫的完整路徑。"""
        if self.rag_qdrant_path.is_absolute():
            return self.rag_qdrant_path

        return PROJECT_ROOT / self.rag_qdrant_path


rag_settings = RagSettings()