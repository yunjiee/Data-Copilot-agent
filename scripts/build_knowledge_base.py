"""
RAG 知識庫離線建庫腳本 (Offline Ingestion Script)

用途：
負責將企業內部文件 (如 .txt, .md) 轉換並寫入 Qdrant 向量資料庫中。
完整流程包含：讀取檔案 -> 文字切塊 (Chunking) -> 計算向量 (Embedding) -> 寫入資料庫 (Qdrant)。

執行時機：
- 系統初次建置，需要匯入第一批知識庫資料時。
- 當公司有新規定或文件修改，放入 `data/knowledge_base` 後，需手動執行此腳本更新資料庫。
平時日常啟動 Agent 進行對話時「不需要」執行此腳本。
"""


import sys
from pathlib import Path

# 將專案根目錄加入 sys.path，解決 ModuleNotFoundError
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_server.chunker import TextChunker
from mcp_servers.rag_server.config import rag_settings
from mcp_servers.rag_server.embedding_service import EmbeddingService
from mcp_servers.rag_server.ingestion_service import IngestionService
from mcp_servers.rag_server.vector_store import QdrantVectorStore


def main() -> None:
    # 直接實例化，模組內部會自動讀取 rag_settings 的設定值
    chunker = TextChunker()

    embedding_service = EmbeddingService()

    vector_store = QdrantVectorStore(
        collection_name=rag_settings.rag_collection_name,
    )

    # 流程協調者
    ingestion_service = IngestionService(  
        chunker=chunker,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    try:
        print("開始建立知識庫...")
        result = ingestion_service.ingest_directory(
            source_dir=rag_settings.source_dir,
            recreate_collection=True,
        )

        print("✅ 知識庫建立完成")
        print(f"文件數量：{result.get('document_count', 0)}")
        print(f"Chunk 數量：{result.get('chunk_count', 0)}")
        print(f"寫入數量：{result.get('inserted_count', 0)}")
        print(f"Collection 總數：{result.get('total_count', 0)}")
    except Exception as e:
        print(f"❌ 建立知識庫時發生錯誤：{e}")
    finally:
        # 確保關閉 Qdrant Vector Store 連線
        vector_store.close()


if __name__ == "__main__":
    main()