"""
檢查 LangChain 版切塊結果，並與原版 TextChunker 並排比較。
不需要載入 Embedding 模型，可以最先執行。

執行：
    uv run python scripts/RAG_langchain/test_splitter.py

比較項目：
- 切塊數量
- 「混合章節」切塊數：一個切塊橫跨超過一個章節
- 章節標註：原版以切塊起點往回找標題，LangChain 版來自 metadata
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_langchain_server.config import lc_rag_settings
from mcp_servers.rag_langchain_server.loaders import load_documents
from mcp_servers.rag_langchain_server.splitters import MarkdownSectionSplitter
from mcp_servers.rag_server.chunker import TextChunker


def sections_in(text: str) -> list[str]:
    """找出切塊內容裡出現的 ## 標題（代表跨入了哪些章節）。"""
    return re.findall(r"^##\s+(.+)$", text, flags=re.MULTILINE)


def section_count(body: str) -> int:
    """
    估計切塊橫跨幾個章節：
    第一個 ## 標題之前若有實質內容（不含 # 大標與分隔線），算一個章節，
    再加上切塊內出現的 ## 標題數。
    """
    lead = re.split(r"^##\s+", body, maxsplit=1, flags=re.MULTILINE)[0]
    lead = re.sub(r"^#\s+.*$|^-{3,}$", "", lead, flags=re.MULTILINE).strip()
    return (1 if lead else 0) + len(sections_in(body))


def body_of(chunk_text: str) -> str:
    return chunk_text.split("內容：\n", 1)[-1]


def label_of(chunk_text: str) -> str:
    return chunk_text.splitlines()[1].replace("章節：", "")


def main() -> None:
    documents = load_documents(lc_rag_settings.source_dir)
    print(f"讀取文件數：{len(documents)}\n")

    lc_splitter = MarkdownSectionSplitter()
    native_chunker = TextChunker()

    for document in documents:
        source = document.metadata["source"]
        lc_chunks = lc_splitter.split_document(document)
        native_chunks = native_chunker.split_text(document.page_content, source=source)

        native_mixed = sum(section_count(body_of(c.text)) > 1 for c in native_chunks)
        lc_mixed = sum(section_count(body_of(c.page_content)) > 1 for c in lc_chunks)

        print("=" * 72)
        print(f"📄 {source}")
        print(f"   切塊數　　　：原版 {len(native_chunks):>2}　｜　LangChain 版 {len(lc_chunks):>2}")
        print(f"   混合章節切塊：原版 {native_mixed:>2}　｜　LangChain 版 {lc_mixed:>2}")

        print("\n   【原版】標註的章節 vs 實際包含的章節")
        for c in native_chunks:
            print(f"   [{c.chunk_index}] 標註：{label_of(c.text)}")
            print(
                f"       內含 ## 標題：{'、'.join(sections_in(body_of(c.text))) or '(無)'}"
                f"　→ 橫跨 {section_count(body_of(c.text))} 個章節"
            )

        print("\n   【LangChain 版】每個切塊的章節")
        for c in lc_chunks:
            print(
                f"   [{c.metadata['chunk_index']:>2}] {c.metadata['heading']}"
                f"  ({len(body_of(c.page_content))} 字)"
            )
        print()

    sample = lc_splitter.split_document(documents[-1])[6]
    print("=" * 72)
    print("LangChain 版範例切塊完整內容：")
    print(sample.page_content)
    print("\nmetadata：", sample.metadata)


if __name__ == "__main__":
    main()
