"""mcp_servers/rag_langchain_server/retrieval_chain.py

以 LCEL（LangChain Expression Language）組出檢索鏈：

    問題 ─→ [相似度搜尋 Runnable] ─→ [格式化 Runnable] ─→ 給 LLM 閱讀的字串

與原版 RetrievalService 的差異：
- 原版在一個 retrieve() 方法裡依序寫死：embed_query → search → 格式化。
- 這裡把每一步做成 Runnable，用「|」串接。
  之後要換檢索方式（例如 MMR、MultiQueryRetriever）或加 reranker，
  只需要替換或插入其中一個 Runnable，其餘步驟不用改。
"""

from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore


def format_docs_with_scores(results: list[tuple[Document, float]]) -> str:
    """
    將檢索結果格式化為 LLM 容易閱讀的文字。
    輸出格式與原版 RetrievalService 相同，Agent 端的 prompt 不需要調整。
    """
    if not results:
        return "⚠️ 在知識庫中找不到相關的資料。"

    lines = ["以下是從知識庫中檢索到的相關參考資料：\n"]
    for i, (doc, score) in enumerate(results, 1):
        source = doc.metadata.get("source", "unknown")
        lines.append(
            f"【資料來源 {i}】 {source} (相似度: {score:.4f})\n"
            f"內容：{doc.page_content}\n"
        )
    return "\n".join(lines)


class LangChainRetrievalService:
    """負責將自然語言問題轉成檢索結果（LangChain 版）。"""

    def __init__(self, vector_store: QdrantVectorStore) -> None:
        self.vector_store = vector_store

    def as_retriever(self, top_k: int = 3) -> VectorStoreRetriever:
        """
        LangChain 標準 Retriever（回傳 Document 清單，不含分數）。
        提供給評估腳本或其他 LangChain 元件（例如 MultiQueryRetriever）使用。
        """
        return self.vector_store.as_retriever(search_kwargs={"k": top_k})

    def build_chain(self, top_k: int = 3) -> Runnable:
        """
        組出檢索鏈。

        使用 similarity_search_with_score 而不是 as_retriever()，
        因為 as_retriever() 預設不回傳相似度分數，而原版輸出有分數。
        """
        if not 1 <= top_k <= 20:
            raise ValueError("top_k 必須介於 1 到 20。")

        def search(query: str) -> list[tuple[Document, float]]:
            cleaned = query.strip()
            if not cleaned:
                raise ValueError("查詢內容不可為空")
            return self.vector_store.similarity_search_with_score(cleaned, k=top_k)

        return RunnableLambda(search) | RunnableLambda(format_docs_with_scores)

    def retrieve(self, query: str, top_k: int = 3) -> str:
        """與原版 RetrievalService.retrieve 相同的介面。"""
        return self.build_chain(top_k=top_k).invoke(query)
