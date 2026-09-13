from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

# 操作 Qdrant 的 QdrantClient 類別，以及提供資料結構與設定類別的 models 模組
from qdrant_client import QdrantClient, models

from mcp_servers.rag_server.chunker import DocumentChunk
from mcp_servers.rag_server.config import (
    RagSettings,
    rag_settings,
)

# 建立檢索結果資料類別
from dataclasses import dataclass

@dataclass(frozen=True)
class VectorSearchResult:
    """代表一筆 Qdrant 向量檢索結果。"""

    point_id: str
    score: float
    text: str
    source: str
    chunk_index: int
    start_char: int
    end_char: int


class QdrantVectorStore:
    """負責操作本機 Qdrant 向量資料庫。"""

    def __init__(
        self,
        settings: RagSettings = rag_settings,
        collection_name: str | None = None,
    ) -> None:
        self.settings = settings

        # 正式執行時使用 .env 的 Collection 名稱；
        # 測試時可以傳入另一個名稱，避免污染正式 Collection。
        self.collection_name = (
            collection_name
            or settings.rag_collection_name
        )

        # 如果資料夾不存在，就自動建立。
        self.settings.qdrant_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 使用 Qdrant Local Mode。
        # 資料會儲存在 data/qdrant，而不是只放在記憶體。
        self.client = QdrantClient(
            path=str(self.settings.qdrant_path)
        )

    def collection_exists(self) -> bool:
        """檢查指定 Collection 是否已存在。"""
        return self.client.collection_exists(
            collection_name=self.collection_name,
        )
        
    def delete_collection(self) -> None:
        """刪除現有的 Collection。"""
        if self.collection_exists():
            self.client.delete_collection(
                collection_name=self.collection_name
            )

    def ensure_collection(
        self,
        vector_size: int,
    ) -> None:
        """
        確保 Collection 已建立。

        若不存在，就建立指定向量維度與 Cosine 距離的
        Collection。
        """
        if self.collection_exists():
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    # 寫入 Point
    def upsert_chunks(
        self,
        chunks: Sequence[DocumentChunk],
        vectors: Sequence[Sequence[float]],
    ) -> int:
        """
        將文件片段、向量及 metadata 寫入 Qdrant。

        Returns:
            寫入的 Point 數量。
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                "chunks 與 vectors 的數量必須相同。"
            )

        if not chunks:
            return 0

        points: list[models.PointStruct] = []

        for chunk, vector in zip(
            chunks,
            vectors,
            strict=True,
        ):
            point_id = self._create_point_id(chunk)

            #向量資料庫中存放的內容
            point = models.PointStruct(
                id=point_id, # 識別ID
                vector=list(vector), #用來計算語意相似度
                payload={        #保存原始文字、來源與其他資訊
                    "text": chunk.text,
                    "source": chunk.source,
                    "chunk_index": chunk.chunk_index,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                },
            )

            points.append(point)

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

        return len(points)

    def count_points(self) -> int:
        """取得目前 Collection 內的 Point 數量。"""
        if not self.collection_exists():
            return 0

        result = self.client.count(
            collection_name=self.collection_name,
            exact=True,
        )

        return result.count

    @staticmethod
    def _create_point_id(
        chunk: DocumentChunk,
    ) -> str:
        """
        根據來源檔案與片段編號，建立固定 UUID。

        同一個來源、同一個 chunk_index 重複寫入時，
        會更新既有 Point，而不會一直新增重複資料。
        """
        identity = (
            f"{chunk.source}:"
            f"{chunk.chunk_index}"
        )

        return str(
            uuid5(
                NAMESPACE_URL,
                identity,
            )
        )

    def search(
        self,
        query_vector: Sequence[float],
        limit: int,
    ) -> list[VectorSearchResult]:
        """
        使用查詢向量搜尋最相似的文件片段。

        Args:
            query_vector:
                使用者問題產生的查詢向量。

            limit:
                最多回傳幾筆結果。

        Returns:
            按相似度由高到低排列的檢索結果。
        """
        if not self.collection_exists():
            raise RuntimeError(
                f"Qdrant Collection 不存在："
                f"{self.collection_name}"
            )

        if not query_vector:
            raise ValueError("查詢向量不可為空。")

        if not 1 <= limit <= 20:
            raise ValueError(
                "limit 必須介於 1 到 20。"
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=list(query_vector),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        results: list[VectorSearchResult] = []

        for point in response.points:
            payload = point.payload or {}

            results.append(
                VectorSearchResult(
                    point_id=str(point.id),
                    score=float(point.score),
                    text=str(payload.get("text", "")),
                    source=str(
                        payload.get("source", "unknown")
                    ),
                    chunk_index=int(
                        payload.get("chunk_index", -1)
                    ),
                    start_char=int(
                        payload.get("start_char", -1)
                    ),
                    end_char=int(
                        payload.get("end_char", -1)
                    ),
                )
            )

        return results


    def close(self) -> None:
        """關閉 Qdrant Client。"""
        self.client.close()