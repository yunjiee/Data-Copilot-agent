import sys
from pathlib import Path

# 將專案根目錄加入 sys.path，解決 ModuleNotFoundError
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.rag_server.chunker import TextChunker


def main() -> None:
    chunker = TextChunker()

    # 建立超過 500 字元的測試內容
    test_document = (
        "第一部分：商品績效分析可以使用營收、銷售數量、"
        "訂單數與退貨率等指標進行評估。"
        * 8
        + "\n\n"
        + "第二部分：退貨率可用退貨商品數除以已售商品數計算，"
        "並用來觀察商品售出後的退貨情況。"
        * 8
        + "\n\n"
        + "第三部分：向量檢索會先將使用者問題轉成查詢向量，"
        "再與知識庫內的文件向量比較相似程度。"
        * 8
    )

    chunks = chunker.split_text(
        text=test_document,
        source="test_ecommerce_knowledge.txt",
    )

    print(f"完整文件字元數：{len(test_document)}")
    print(f"切割片段數量：{len(chunks)}")
    print(
        f"Chunk Size：{chunker.chunk_size}"
    )
    print(
        f"Chunk Overlap：{chunker.chunk_overlap}"
    )

    for chunk in chunks:
        print("\n" + "=" * 60)

        print(f"片段編號：{chunk.chunk_index}")
        print(f"文件來源：{chunk.source}")
        print(
            f"字元範圍："
            f"{chunk.start_char}～{chunk.end_char}"
        )
        print(f"片段長度：{len(chunk.text)}")

        print("\n片段前 100 字：")
        print(chunk.text[:100])

        print("\n片段後 100 字：")
        print(chunk.text[-100:])
        
    if len(chunks) >= 2:
        overlap_size = chunker.chunk_overlap

        first_chunk_tail = chunks[0].text[-overlap_size:]
        second_chunk_head = chunks[1].text[:overlap_size]

        print("\n" + "=" * 60)
        print("檢查第一與第二片段的重疊內容：")
        print(
            "是否完全相同：",
            first_chunk_tail == second_chunk_head,
        )


if __name__ == "__main__":
    main()