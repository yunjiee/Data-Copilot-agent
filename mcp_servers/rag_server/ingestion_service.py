'''
離線建庫流程的協調者:

知識文件
  ↓
讀取文件
  ↓
TextChunker 切塊
  ↓
EmbeddingService 產生向量
  ↓
QdrantVectorStore 寫入 Qdrant
'''

from pathlib import Path

from mcp_servers.rag_server.chunker import DocumentChunk, TextChunker
from mcp_servers.rag_server.embedding_service import EmbeddingService
from mcp_servers.rag_server.vector_store import QdrantVectorStore


class IngestionService:
    """負責載入知識文件、切塊、向量化並寫入 Qdrant。"""

    SUPPORTED_SUFFIXES = {
        ".md",
        ".txt",
    }

    def __init__(
        self,
        chunker: TextChunker,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
    ) -> None:
        self.chunker = chunker
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def scan_documents(
        self,
        source_dir: Path,
    ) -> list[Path]:
        """掃描知識庫資料夾中的 Markdown 與 TXT 文件。"""

        if not source_dir.exists():
            raise FileNotFoundError(
                f"知識庫資料夾不存在：{source_dir}"
            )

        if not source_dir.is_dir():
            raise NotADirectoryError(
                f"知識庫路徑不是資料夾：{source_dir}"
            )

        document_paths = [
            path
            for path in source_dir.rglob("*")
            if (
                path.is_file()
                and path.suffix.lower()
                in self.SUPPORTED_SUFFIXES
            )
        ]

        return sorted(document_paths)

    def load_document(
        self,
        file_path: Path,
    ) -> str:
        """讀取單一 Markdown 或 TXT 文件。"""

        try:
            return file_path.read_text(
                encoding="utf-8",
            ).strip()

        except UnicodeDecodeError as exc:
            raise ValueError(
                f"文件不是 UTF-8 編碼：{file_path}"
            ) from exc

    def build_chunks(
        self,
        file_path: Path,
        text: str,
    ) -> list[DocumentChunk]:
        """將單一文件切成包含 metadata 的 Chunk。"""

        # 直接回傳 Chunker 處理好的 DocumentChunk 列表
        return self.chunker.split_text(
            text=text,
            source=file_path.name,
        )

    def ingest_directory(
        self,
        source_dir: Path,
        recreate_collection: bool = True,
    ) -> dict[str, int]:
        """
        掃描資料夾並建立 Qdrant 向量索引。

        Args:
            source_dir:
                原始知識文件所在資料夾。

            recreate_collection:
                是否先刪除舊 Collection 後再重建。

        Returns:
            建庫結果統計。
        """

        document_paths = self.scan_documents(
            source_dir=source_dir,
        )

        if not document_paths:
            raise ValueError(
                "知識庫資料夾中沒有 .md 或 .txt 文件："
                f"{source_dir}"
            )

        all_chunks: list[DocumentChunk] = []
        loaded_document_count = 0

        for file_path in document_paths:
            text = self.load_document(
                file_path=file_path,
            )

            if not text:
                print(
                    f"略過空白文件：{file_path.name}"
                )
                continue

            file_chunks = self.build_chunks(
                file_path=file_path,
                text=text,
            )

            all_chunks.extend(file_chunks)
            loaded_document_count += 1

            print(
                f"已處理文件：{file_path.name}，"
                f"Chunk 數量：{len(file_chunks)}"
            )

        if not all_chunks:
            raise ValueError(
                "沒有產生任何 Chunk，無法建立向量索引。"
            )

        chunk_texts = [
            chunk.text
            for chunk in all_chunks
        ]

        vectors = (
            self.embedding_service.embed_passages(
                chunk_texts
            )
        )

        if len(vectors) != len(all_chunks):
            raise RuntimeError(
                "Chunk 數量與 Embedding 數量不一致："
                f"chunks={len(all_chunks)}, "
                f"vectors={len(vectors)}"
            )

        if recreate_collection:
            self.vector_store.delete_collection()

        self.vector_store.ensure_collection(
            vector_size=self.embedding_service.vector_size,
        )

        inserted_count = self.vector_store.upsert_chunks(
            chunks=all_chunks,
            vectors=vectors,
        )

        total_count = (
            self.vector_store.count_points()
        )

        return {
            "document_count": (
                loaded_document_count
            ),
            "chunk_count": len(all_chunks),
            "inserted_count": inserted_count,
            "total_count": total_count,
        }