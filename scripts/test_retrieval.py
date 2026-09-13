"""
測試檢索 (Retrieval) 功能是否正常運作。
模擬使用者輸入問題，測試 Qdrant 是否能回傳最相關的文件片段。
"""

import sys
from pathlib import Path

# 將專案根目錄加入 sys.path，解決 ModuleNotFoundError
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_server.config import rag_settings
from mcp_servers.rag_server.embedding_service import EmbeddingService
from mcp_servers.rag_server.vector_store import QdrantVectorStore


def main() -> None:
    print("初始化檢索工具...")
    
    # 1. 準備 Embedding 服務 (用來把「問題」轉成向量)
    embedding_service = EmbeddingService()

    # 2. 連線到剛才建好的「正式」 Qdrant 資料庫
    vector_store = QdrantVectorStore(
        collection_name=rag_settings.rag_collection_name,
    )

    # 3. 測試問題 (請換成你知識庫裡面實際有的內容)
    query = "退貨率要怎麼計算？"
    print(f"\n❓ 測試問題: {query}\n")
    print("-" * 50)

    try:
        if not vector_store.collection_exists():
            raise RuntimeError(
                "正式 Collection 尚未建立，請先執行：\n"
                "python scripts/build_knowledge_base.py"
            )

        # 4. 將使用者的問題轉換為向量
        query_vector = embedding_service.embed_query(query)

        point_count = vector_store.count_points()
        print(f"資料庫內共有 {point_count} 筆文件片段。\n")
        
        # 5. 去 Qdrant 搜尋最相近的 3 筆資料
        results = vector_store.search(query_vector=query_vector, limit=3)

        # 6. 印出結果檢查
        for i, res in enumerate(results, 1):
            print(f"[{i}] 相似度分數: {res.score:.4f}")
            print(f"來源: {res.source} (Chunk: {res.chunk_index})")
            # 只印出前 150 個字，避免畫面太滿
            print(f"內容: {res.text[:150]}...\n")
            print("-" * 50)
            
    finally:
        vector_store.close()


if __name__ == "__main__":
    main()