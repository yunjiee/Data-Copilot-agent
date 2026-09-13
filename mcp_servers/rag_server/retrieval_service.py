from mcp_servers.rag_server.embedding_service import EmbeddingService
from mcp_servers.rag_server.vector_store import QdrantVectorStore


class RetrievalService:
    """負責將自然語言問題轉化為檢索結果，並格式化為 LLM 容易閱讀的文字。"""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 3) -> str:
        """
        搜尋知識庫，並回傳格式化後的文字結果。
        """
        # 1. 檢查知識庫狀態
        if not self.vector_store.collection_exists():
            return "⚠️ 知識庫尚未建立，無法進行檢索。"

        # 2. 將問題轉成向量
        query_vector = self.embedding_service.embed_query(query)

        # 3. 搜尋相似度最高的片段
        results = self.vector_store.search(
            query_vector=query_vector,
            limit=top_k,
        )

        if not results:
            return "⚠️ 在知識庫中找不到相關的資料。"

        # 4. 格式化輸出，讓 LLM (AI Agent) 能看懂
        formatted_texts = ["以下是從知識庫中檢索到的相關參考資料：\n"]
        
        for i, res in enumerate(results, 1):
            formatted_texts.append(
                f"【資料來源 {i}】 {res.source} (相似度: {res.score:.4f})\n"
                f"內容：{res.text}\n"
            )

        return "\n".join(formatted_texts)