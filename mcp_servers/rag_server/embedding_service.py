from collections.abc import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer
from mcp_servers.rag_server.config import RagSettings, rag_settings

# 把文字轉成向量，並統一管理 Embedding 模型的載入與使用方式。

class EmbeddingService:
    """負責將查詢與文件轉換成向量。"""

    def __init__(
        self,
        settings: RagSettings = rag_settings,
    ) -> None:
        self.settings = settings

        self.model = SentenceTransformer(
            self.settings.rag_embedding_model
        )

    @property
    def vector_size(self) -> int:
        """取得 Embedding 模型輸出的向量維度。"""
        dimension = self.model.get_embedding_dimension()

        if dimension is None:
            raise RuntimeError("無法取得 Embedding 模型向量維度")

        return dimension

    def embed_passages(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """
        將知識文件片段轉換成向量。

        E5 文件檢索必須加上 passage: 前綴。
        """
        cleaned_texts = [
            text.strip()
            for text in texts
            if text and text.strip()
        ]

        if not cleaned_texts:
            return []

        prepared_texts = [
            f"passage: {text}"
            for text in cleaned_texts
        ]

        embeddings: np.ndarray = self.model.encode(
            prepared_texts,
            batch_size=self.settings.rag_embedding_batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return embeddings.tolist()

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        """
        將使用者問題轉換成查詢向量。

        E5 查詢必須加上 query: 前綴。
        """
        cleaned_query = query.strip()

        if not cleaned_query:
            raise ValueError("查詢內容不可為空")

        prepared_query = f"query: {cleaned_query}"

        embedding: np.ndarray = self.model.encode(
            prepared_query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return embedding.tolist()