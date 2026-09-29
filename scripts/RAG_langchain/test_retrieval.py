"""
測試 LangChain 版檢索鏈。

執行前請先建庫：
    uv run python scripts/RAG_langchain/build_knowledge_base.py

執行：
    uv run python scripts/RAG_langchain/test_retrieval.py
    uv run python scripts/RAG_langchain/test_retrieval.py "高價值商品怎麼判定？"
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_langchain_server.embeddings import E5Embeddings
from mcp_servers.rag_langchain_server.retrieval_chain import LangChainRetrievalService
from mcp_servers.rag_langchain_server.vector_store import open_vector_store


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "退貨率要怎麼計算？"

    print("初始化 LangChain 檢索鏈...")
    embedding = E5Embeddings()
    vector_store = open_vector_store(embedding=embedding)
    service = LangChainRetrievalService(vector_store=vector_store)

    try:
        print(f"\n❓ 測試問題：{query}\n")
        print("-" * 60)

        # 1. 直接看 Retriever 回傳的 Document 與 metadata
        docs = service.as_retriever(top_k=3).invoke(query)
        for i, doc in enumerate(docs, 1):
            print(f"[{i}] {doc.metadata['source']} ｜ {doc.metadata['heading']}")
        print("-" * 60)

        # 2. 完整檢索鏈的輸出（這就是 MCP Tool 回傳給 Agent 的內容）
        print(service.retrieve(query=query, top_k=3))
    finally:
        vector_store.client.close()


if __name__ == "__main__":
    main()
