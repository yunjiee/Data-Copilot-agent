"""原生版 RAG 檢索品質評估腳本。

使用固定題集評估原生 Retriever 的 Recall@K、MRR 與來源正確率。
執行前請確認已建庫：
    uv run python scripts/RAG/build_knowledge_base.py

執行：
    uv run python scripts/RAG/evaluate_retrieval.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_server.config import rag_settings
from mcp_servers.rag_server.embedding_service import EmbeddingService
from mcp_servers.rag_server.vector_store import QdrantVectorStore

CANDIDATE_PATHS = [
    PROJECT_ROOT / "scripts" / "eval" / "eval_questions.json",
    PROJECT_ROOT / "scripts" / "RAG_langchain" / "eval" / "eval_questions.json",
    PROJECT_ROOT / "eval" / "eval_questions.json",
]


def find_questions_path() -> Path | None:
    for path in CANDIDATE_PATHS:
        if path.exists():
            return path
    return None

K_VALUES = (1, 3, 5)
MAX_K = max(K_VALUES)


def normalize(text: str) -> str:
    return "".join(text.split())


def is_hit(source: str, text: str, item: dict) -> bool:
    return (
        source == item["expected_source"]
        and normalize(item["expected_keyword"]) in normalize(text)
    )


def main() -> None:
    questions_path = find_questions_path()
    if not questions_path:
        print("❌ 找不到評估題集 eval_questions.json，已嘗試路徑：")
        for p in CANDIDATE_PATHS:
            print(f"  - {p}")
        return

    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    print(f"載入題集：{len(questions)} 題")

    embedding_service = EmbeddingService()
    store = QdrantVectorStore(collection_name=rag_settings.rag_collection_name)

    hits_at_k = {k: 0 for k in K_VALUES}
    reciprocal_ranks: list[float] = []
    misses: list[str] = []

    try:
        for item in questions:
            vector = embedding_service.embed_query(item["question"])
            results = store.search(query_vector=vector, limit=MAX_K)

            first_hit_rank = next(
                (rank for rank, r in enumerate(results, 1)
                 if is_hit(r.source, r.text, item)),
                None,
            )

            for k in K_VALUES:
                if first_hit_rank is not None and first_hit_rank <= k:
                    hits_at_k[k] += 1

            reciprocal_ranks.append(1 / first_hit_rank if first_hit_rank else 0.0)
            if first_hit_rank is None:
                misses.append(f"Q{item['id']} {item['question']}")

        total = len(questions)
        print("\n" + "=" * 50)
        print(f"原生 RAG 檢索評估結果（題數：{total}）")
        print("=" * 50)
        for k in K_VALUES:
            print(f"Recall@{k:<4} : {hits_at_k[k] / total:.2%}")
        print(f"MRR        : {sum(reciprocal_ranks) / total:.3f}")

        if misses:
            print(f"\n未命中題目（Top-{MAX_K} 外）：")
            for miss in misses:
                print(f"  - {miss}")
        else:
            print("\n🎉 所有題目皆在前 5 筆內命中！")
    finally:
        store.close()


if __name__ == "__main__":
    main()