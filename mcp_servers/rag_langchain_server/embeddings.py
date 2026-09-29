"""mcp_servers/rag_langchain_server/embeddings.py

實作 LangChain 的 Embeddings 介面，包裝 E5 模型。

為什麼自己實作而不直接用現成的 HuggingFaceEmbeddings：
- E5 模型要求文件加上「passage: 」、查詢加上「query: 」前綴，
  少了前綴檢索品質會明顯下降。
- 繼承 Embeddings 並實作 embed_documents / embed_query 兩個方法，
  就能直接交給 LangChain 的任何 VectorStore 使用，
  同時把 E5 的前綴規則封裝在這一層，其他元件不需要知道。
"""

from collections.abc import Sequence

from langchain_core.embeddings import Embeddings

from mcp_servers.rag_langchain_server.config import (
    LangChainRagSettings,
    lc_rag_settings,
)


class E5Embeddings(Embeddings):
    """E5 系列模型的 LangChain Embeddings 實作。"""

    def __init__(
        self,
        settings: LangChainRagSettings = lc_rag_settings,
    ) -> None:
        # 延遲 import：只有真正建立模型時才載入 PyTorch
        from sentence_transformers import SentenceTransformer

        self.batch_size = settings.embedding_batch_size
        self.model = SentenceTransformer(settings.embedding_model)

    @property
    def vector_size(self) -> int:
        """模型輸出的向量維度。"""
        dimension = self.model.get_embedding_dimension()
        if dimension is None:
            raise RuntimeError("無法取得 Embedding 模型向量維度")
        return dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """
        將文件切塊轉成向量。

        注意：輸入幾筆就必須回傳幾筆，順序也必須一致，
        VectorStore 會依位置把向量和文件配對。
        因此這裡不過濾空字串（空字串應在切塊階段就排除）。
        """
        if not texts:
            return []

        embeddings = self.model.encode(
            [f"passage: {text}" for text in texts],
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """將使用者問題轉成查詢向量。"""
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("查詢內容不可為空")

        embedding = self.model.encode(
            f"query: {cleaned}",
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embedding.tolist()
