import sys
from pathlib import Path

# 將專案根目錄加入 sys.path，解決 ModuleNotFoundError
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_server.chunker import TextChunker
from mcp_servers.rag_server.config import rag_settings
from mcp_servers.rag_server.embedding_service import (
    EmbeddingService,
)
from mcp_servers.rag_server.vector_store import (
    QdrantVectorStore,
)


def find_target_file() -> Path:
    """尋找要測試的知識庫文件。"""

    source_dir = rag_settings.source_dir
    md_files = list(source_dir.rglob("*.md"))
    
    if not md_files:
        raise FileNotFoundError(
            f"在 {source_dir} 中找不到任何 Markdown 檔案！請確認資料夾內有 .md 檔案。"
        )
        
    # 自動取第一個找到的檔案來進行測試
    return md_files[0]


def main() -> None:
    """
    測試流程：

    測試文件
        → 文件切塊
        → 產生文件向量
        → 建立 Qdrant Collection
        → 寫入向量與 Payload
        → 確認 Point 數量
    """

    file_path = find_target_file()

    print(f"[FILE] {file_path}")

    text = file_path.read_text(encoding="utf-8")

    # 1. 建立文件切塊工具
    chunker = TextChunker()

    # 2. 建立 Embedding 服務
    embedding_service = EmbeddingService()

    # 3. 使用測試用 Collection，避免寫入正式 Collection
    test_collection_name = (
        f"{rag_settings.rag_collection_name}_test_v2"
    )

    # 4. 建立 Qdrant Vector Store
    vector_store = QdrantVectorStore(
        collection_name=test_collection_name,
    )

    try:

        # 測試時先完整刪除上一輪 Collection
        if vector_store.collection_exists():
            print(
                f"刪除舊測試 Collection："
                f"{test_collection_name}"
            )

            vector_store.client.delete_collection(
                collection_name=test_collection_name,
            )
        if vector_store.collection_exists():
            raise RuntimeError(
                f"Collection 沒有成功刪除：{test_collection_name}"
            )
        print("已確認舊 Collection 不存在")


        # 2. 顯示本次真正使用的文件
        print(f"目前執行檔案：{__file__}")
        print(f"測試文件總長度：{len(text)}")
        print(f"Chunk Size：{chunker.chunk_size}")
        print(f"Chunk Overlap：{chunker.chunk_overlap}")

        # 5. 將完整文件切成多個 DocumentChunk
        chunks = chunker.split_text(
            text=text,             # 真正被切割的實際檔案內容
            source=file_path.name, # 將真實檔名傳入，讓 Chunker 萃取
        )

        # 6. 取出各片段的純文字
        chunk_texts = [
            chunk.text
            for chunk in chunks
        ]

        # 7. 將各片段轉成向量
        vectors = embedding_service.embed_passages(
            chunk_texts
        )

        # 8. 刪除後，重新建立 Qdrant Collection
        # 寫入前檢查是否是 0 筆也正確
        vector_store.ensure_collection(
            vector_size=embedding_service.vector_size,
        )

        empty_count = vector_store.count_points()

        assert empty_count == 0, (
            f"新建 Collection 應為 0 筆，"
            f"但目前有 {empty_count} 筆。"
        )

        # 9. 將 Chunk、向量與 Payload 寫入 Qdrant
        inserted_count = vector_store.upsert_chunks(
            chunks=chunks,
            vectors=vectors,
        )

        # 10. 查詢 Collection 中目前的 Point 數量
        total_count = vector_store.count_points()

        print("\nQdrant Vector Store 測試完成")
        print("=" * 60)

        print(f"Collection 名稱：{test_collection_name}")
        print(f"Qdrant 儲存路徑：{rag_settings.qdrant_path}")
        print(f"文件片段數量：{len(chunks)}")
        print(f"文件向量數量：{len(vectors)}")
        print(f"每筆向量維度：{embedding_service.vector_size}")
        print(f"本次寫入 Point 數量：{inserted_count}")
        print(f"Collection Point 總數：{total_count}")

        # 基本測試驗證
        assert len(chunks) > 0, "文件沒有成功切塊。"

        assert len(chunks) == len(vectors), (
            "文件片段數量和向量數量不一致。"
        )

        assert inserted_count == len(chunks), (
            "寫入數量和文件片段數量不一致。"
        )

        assert total_count == inserted_count, (
            f"Chunk 數量為 {len(chunks)} 段，"
            f"但 Qdrant Point 數量為 {total_count} 筆。"
        )

        print("\n測試驗證：全部通過")

        # 為了驗證 Chunker 修改後的「標題萃取」效果，印出前三個片段來檢查
        print("\n=== 驗證 Chunker 標題萃取效果 ===")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n[第 {i+1} 個片段]")
            print("-" * 40)
            print(f"字元範圍：{chunk.start_char}～{chunk.end_char}")
            print(f"片段長度：{len(chunk.text)}")
            print("片段內容：\n")
            print(chunk.text)

        print("\n第一筆向量前五個數值：")
        print(vectors[0][:5])

    finally:
        # 無論成功或發生錯誤，都關閉 Qdrant Client
        vector_store.close()


if __name__ == "__main__":
    main()