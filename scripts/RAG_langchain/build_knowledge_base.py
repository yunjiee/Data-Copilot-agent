"""
LangChain 版 RAG 知識庫離線建庫腳本。

執行：
    uv run python scripts/RAG_langchain/build_knowledge_base.py

結果寫入 data/qdrant_langchain（與原版 data/qdrant 分開）。
知識文件有更新時才需要重新執行。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_langchain_server.config import lc_rag_settings
from mcp_servers.rag_langchain_server.embeddings import E5Embeddings
from mcp_servers.rag_langchain_server.ingestion import ingest_directory


def main() -> None:
    print("🚀 啟動 LangChain 版建庫程序（載入 Embedding 模型中，請稍候）...")
    print(f"知識文件：{lc_rag_settings.source_dir}")
    print(f"Qdrant 路徑：{lc_rag_settings.qdrant_path}")
    print(f"Collection：{lc_rag_settings.collection_name}\n")

    embedding = E5Embeddings()
    print(f"Embedding 模型：{lc_rag_settings.embedding_model}（{embedding.vector_size} 維）\n")

    try:
        result = ingest_directory(embedding=embedding, recreate_collection=True)
        print("\n✅ 知識庫建立完成")
        print(f"文件數量：{result['document_count']}")
        print(f"切塊數量：{result['chunk_count']}")
        print(f"Collection 總數：{result['total_count']}")
    except Exception as e:
        print(f"❌ 建立知識庫時發生錯誤：{e}")
        raise


if __name__ == "__main__":
    main()
