"""
以固定題集比較「原版手寫 RAG」與「LangChain 版 RAG」的檢索品質。

執行前兩版都必須先建庫：
    uv run python scripts/RAG/build_knowledge_base.py
    uv run python scripts/RAG_langchain/build_knowledge_base.py

執行：
    uv run python scripts/eval/compare_retrievers.py

評估方式：
- 命中判斷：檢索結果的「來源檔名」等於 expected_source，
  且內容包含 expected_keyword，才算命中。
  （兩版切法不同、切塊編號無法對應，所以不能用 chunk id 判斷。）
- Recall@K：前 K 筆結果中有命中的題目比例。
- MRR：第一個命中結果名次的倒數，取平均（前 MAX_K 筆內都沒命中記為 0）。
- 平均字數：前 K 筆結果的內容總長度，反映「送進 LLM 的 context 有多少」。

注意：兩版的切塊大小不同（原版每塊約 500 字、LangChain 版依章節切，多半較短），
相同 K 值下原版帶進的文字量較多。解讀 Recall 時請同時看平均字數。
"""

import json
import sys
from collections.abc import Callable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

QUESTIONS_PATH = Path(__file__).resolve().parent / "eval_questions.json"
K_VALUES = (1, 3, 5)
MAX_K = max(K_VALUES)

# 檢索函式的型別：輸入問題與 K，回傳 [(來源檔名, 內容), ...]
SearchFn = Callable[[str, int], list[tuple[str, str]]]


def normalize(text: str) -> str:
    """移除空白與換行後再比對關鍵字，避免切塊格式差異造成誤判。"""
    return "".join(text.split())


def is_hit(source: str, text: str, item: dict) -> bool:
    return (
        source == item["expected_source"]
        and normalize(item["expected_keyword"]) in normalize(text)
    )


def evaluate(name: str, search: SearchFn, questions: list[dict]) -> dict:
    hits_at_k = {k: 0 for k in K_VALUES}
    reciprocal_ranks: list[float] = []
    context_chars = {k: 0 for k in K_VALUES}
    misses: list[str] = []

    for item in questions:
        results = search(item["question"], MAX_K)

        first_hit_rank = next(
            (rank for rank, (source, text) in enumerate(results, 1)
             if is_hit(source, text, item)),
            None,
        )

        for k in K_VALUES:
            if first_hit_rank is not None and first_hit_rank <= k:
                hits_at_k[k] += 1
            context_chars[k] += sum(len(text) for _, text in results[:k])

        reciprocal_ranks.append(1 / first_hit_rank if first_hit_rank else 0.0)
        if first_hit_rank is None:
            misses.append(f"Q{item['id']} {item['question']}")

    total = len(questions)
    return {
        "name": name,
        "recall": {k: hits_at_k[k] / total for k in K_VALUES},
        "mrr": sum(reciprocal_ranks) / total,
        "avg_chars": {k: context_chars[k] / total for k in K_VALUES},
        "misses": misses,
    }


def build_native_search() -> tuple[SearchFn, Callable[[], None]]:
    """原版：EmbeddingService + 自寫 QdrantVectorStore。"""
    from mcp_servers.rag_server.config import rag_settings
    from mcp_servers.rag_server.embedding_service import EmbeddingService
    from mcp_servers.rag_server.vector_store import QdrantVectorStore

    embedding_service = EmbeddingService()
    store = QdrantVectorStore(collection_name=rag_settings.rag_collection_name)

    def search(query: str, k: int) -> list[tuple[str, str]]:
        vector = embedding_service.embed_query(query)
        return [(r.source, r.text) for r in store.search(query_vector=vector, limit=k)]

    return search, store.close


def build_langchain_search() -> tuple[SearchFn, Callable[[], None]]:
    """LangChain 版：E5Embeddings + langchain_qdrant。"""
    from mcp_servers.rag_langchain_server.embeddings import E5Embeddings
    from mcp_servers.rag_langchain_server.vector_store import open_vector_store

    store = open_vector_store(embedding=E5Embeddings())

    def search(query: str, k: int) -> list[tuple[str, str]]:
        docs = store.similarity_search(query, k=k)
        return [(d.metadata.get("source", "unknown"), d.page_content) for d in docs]

    return search, store.client.close


def print_report(reports: list[dict], total: int) -> None:
    print("\n" + "=" * 72)
    print(f"檢索評估結果（題數：{total}）")
    print("=" * 72)

    header = f"{'指標':<14}" + "".join(f"{r['name']:>18}" for r in reports)
    print(header)
    print("-" * len(header))

    for k in K_VALUES:
        row = f"{f'Recall@{k}':<14}" + "".join(f"{r['recall'][k]:>18.2%}" for r in reports)
        print(row)
    print(f"{'MRR':<14}" + "".join(f"{r['mrr']:>18.3f}" for r in reports))
    for k in K_VALUES:
        row = f"{f'平均字數@{k}':<12}" + "".join(f"{r['avg_chars'][k]:>18.0f}" for r in reports)
        print(row)

    for r in reports:
        print(f"\n【{r['name']}】前 {MAX_K} 筆仍未命中的題目：")
        for miss in r["misses"] or ["（無）"]:
            print(f"  - {miss}")


def main() -> None:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    print(f"載入題集：{len(questions)} 題")

    reports = []
    for name, builder in [("原版 (native)", build_native_search),
                          ("LangChain 版", build_langchain_search)]:
        print(f"\n▶ 評估 {name} ...")
        search, close = builder()
        try:
            reports.append(evaluate(name, search, questions))
        finally:
            close()

    print_report(reports, total=len(questions))


if __name__ == "__main__":
    main()
