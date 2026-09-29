"""mcp_servers/rag_langchain_server/vector_store.py

建立與開啟 langchain_qdrant.QdrantVectorStore。

與原版 QdrantVectorStore（自己包 qdrant_client）的差異：
- 原版自己寫 create_collection、PointStruct、upsert、query_points。
- 這裡交給 langchain_qdrant 處理，payload 會存成 LangChain 的標準格式：
  {"page_content": ..., "metadata": {...}}。
  因此兩版的 Collection 格式不相容，必須各自建庫。
"""

from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from mcp_servers.rag_langchain_server.config import (
    LangChainRagSettings,
    lc_rag_settings,
)


def create_point_id(chunk: Document) -> str:
    """
    以「來源檔名 + 切塊編號」產生固定 UUID。
    重複建庫時同一切塊會得到同一個 ID，不會產生重複資料。
    """
    identity = f"{chunk.metadata['source']}:{chunk.metadata['chunk_index']}"
    return str(uuid5(NAMESPACE_URL, identity))


def build_vector_store(
    chunks: list[Document],
    embedding: Embeddings,
    settings: LangChainRagSettings = lc_rag_settings,
    recreate_collection: bool = True,
) -> QdrantVectorStore:
    """
    將切塊向量化並寫入 Qdrant（離線建庫使用）。

    from_documents 內部會：
    1. 呼叫 embedding.embed_documents 產生向量
    2. 依向量維度建立 Collection（Cosine 距離）
    3. 將 page_content 與 metadata 寫入 payload
    """
    settings.qdrant_path.mkdir(parents=True, exist_ok=True)

    return QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embedding,
        ids=[create_point_id(chunk) for chunk in chunks],
        path=str(settings.qdrant_path),
        collection_name=settings.collection_name,
        force_recreate=recreate_collection,
    )


def collection_exists(
    client: QdrantClient,
    settings: LangChainRagSettings = lc_rag_settings,
) -> bool:
    """檢查 Collection 是否已建立。"""
    return client.collection_exists(collection_name=settings.collection_name)


def open_vector_store(
    embedding: Embeddings,
    settings: LangChainRagSettings = lc_rag_settings,
    client: QdrantClient | None = None,
) -> QdrantVectorStore:
    """
    開啟已建好的 Collection（線上檢索使用）。

    Raises:
        RuntimeError: Collection 尚未建立時。
    """
    if client is None:
        settings.qdrant_path.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(settings.qdrant_path))

    if not collection_exists(client, settings):
        raise RuntimeError(
            f"Qdrant Collection 不存在：{settings.collection_name}，"
            "請先執行 python scripts/RAG_langchain/build_knowledge_base.py"
        )

    return QdrantVectorStore(
        client=client,
        collection_name=settings.collection_name,
        embedding=embedding,
    )
