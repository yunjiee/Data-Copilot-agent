"""mcp_servers/rag_langchain_server/ingestion.py

離線建庫流程：

知識文件
  ↓ loaders.load_documents
Document（metadata: source）
  ↓ MarkdownSectionSplitter
切塊 Document（metadata: source / h1 / h2 / heading / chunk_index）
  ↓ E5Embeddings + QdrantVectorStore.from_documents
寫入 Qdrant（data/qdrant_langchain）
"""

from langchain_core.embeddings import Embeddings

from mcp_servers.rag_langchain_server.config import (
    LangChainRagSettings,
    lc_rag_settings,
)
from mcp_servers.rag_langchain_server.loaders import load_documents
from mcp_servers.rag_langchain_server.splitters import MarkdownSectionSplitter
from mcp_servers.rag_langchain_server.vector_store import build_vector_store


def ingest_directory(
    embedding: Embeddings,
    settings: LangChainRagSettings = lc_rag_settings,
    recreate_collection: bool = True,
) -> dict[str, int]:
    """
    掃描知識庫資料夾並建立 LangChain 版向量索引。

    Returns:
        建庫結果統計（文件數、切塊數、Collection 內總筆數）。
    """
    documents = load_documents(settings.source_dir)
    if not documents:
        raise ValueError(f"知識庫資料夾中沒有 .md 或 .txt 文件：{settings.source_dir}")

    splitter = MarkdownSectionSplitter(settings=settings)
    chunks = splitter.split_documents(documents)
    if not chunks:
        raise ValueError("沒有產生任何切塊，無法建立向量索引。")

    for document in documents:
        count = sum(
            1 for chunk in chunks
            if chunk.metadata["source"] == document.metadata["source"]
        )
        print(f"已處理文件：{document.metadata['source']}，切塊數量：{count}")

    vector_store = build_vector_store(
        chunks=chunks,
        embedding=embedding,
        settings=settings,
        recreate_collection=recreate_collection,
    )

    total_count = vector_store.client.count(
        collection_name=settings.collection_name,
        exact=True,
    ).count
    vector_store.client.close()

    return {
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "total_count": total_count,
    }
