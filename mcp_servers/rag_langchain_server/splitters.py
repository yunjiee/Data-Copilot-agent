"""mcp_servers/rag_langchain_server/splitters.py

兩階段切塊：
1. MarkdownHeaderTextSplitter：先依 Markdown 標題（# / ##）切成章節，
   章節標題寫進 metadata（h1 / h2）。
2. RecursiveCharacterTextSplitter：章節過長時再依字數切，
   並依「段落 → 換行 → 句號 → 分號 → 逗號」的順序找切點，避免把句子切斷。

與原版 TextChunker 的差異：
- 原版在整份文件上以固定字數切，再用切塊「起點」往回找最近的標題。
  一個切塊若跨越兩個章節，後半段內容會被標成前一個章節。
- 這裡先依章節切，每個切塊只會屬於一個章節，章節標註一定正確。
"""

import re

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from mcp_servers.rag_langchain_server.config import (
    LangChainRagSettings,
    lc_rag_settings,
)

# 要切分的標題層級，以及寫入 metadata 的欄位名稱
HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
]

# 中文文件的切點優先順序
CHINESE_SEPARATORS = ["\n\n", "\n", "。", "；", "，", ""]


class MarkdownSectionSplitter:
    """依 Markdown 章節與字數切塊，輸出帶有章節 metadata 的 Document。"""

    def __init__(
        self,
        settings: LangChainRagSettings = lc_rag_settings,
    ) -> None:
        # strip_headers=True：標題文字從內容移除，改由 metadata 保存，
        # 再由 build_chunk_text 統一加回「章節：」前綴，避免標題重複出現。
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS_TO_SPLIT_ON,
            strip_headers=True,
        )

        self.char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=CHINESE_SEPARATORS,
            keep_separator="end",  # 句號、逗號留在前一段的結尾
        )

    @staticmethod
    def get_heading(metadata: dict) -> str:
        """組出章節路徑，例如「電商指標定義 > 六、退貨率」。"""
        parts = [
            metadata[key]
            for _, key in HEADERS_TO_SPLIT_ON
            if metadata.get(key)
        ]
        return " > ".join(parts) if parts else "未指定章節"

    @staticmethod
    def clean_section_text(text: str) -> str:
        """
        清理 MarkdownHeaderTextSplitter 的輸出：
        - 它合併行時會在行尾留下兩個空白（Markdown 換行語法），移除之
        - 移除章節結尾的分隔線「---」
        """
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"(\n\s*-{3,}\s*)+$", "", text.strip())
        return text.strip()

    @staticmethod
    def build_chunk_text(source: str, heading: str, content: str) -> str:
        """
        與原版 TextChunker.build_chunk_text 相同的前綴格式，
        讓兩版比較時的差異只在「怎麼切」，而不是「前綴不同」。
        """
        return (
            f"文件：{source}\n"
            f"章節：{heading}\n"
            f"內容：\n{content.strip()}"
        )

    def split_document(self, document: Document) -> list[Document]:
        """將單一文件切成多個帶有 metadata 的切塊。"""
        source = document.metadata.get("source", "unknown")

        # 第一階段：依章節切
        sections = self.header_splitter.split_text(document.page_content)
        for section in sections:
            section.page_content = self.clean_section_text(section.page_content)

        # 第二階段：章節過長時再依字數切（metadata 會自動沿用）
        pieces = self.char_splitter.split_documents(sections)

        chunks: list[Document] = []
        for chunk_index, piece in enumerate(pieces):
            content = piece.page_content.strip()
            if not content:
                continue

            heading = self.get_heading(piece.metadata)

            chunks.append(
                Document(
                    page_content=self.build_chunk_text(
                        source=source,
                        heading=heading,
                        content=content,
                    ),
                    metadata={
                        **piece.metadata,  # h1 / h2
                        "source": source,
                        "heading": heading,
                        "chunk_index": chunk_index,
                    },
                )
            )

        return chunks

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """切割多份文件。"""
        chunks: list[Document] = []
        for document in documents:
            chunks.extend(self.split_document(document))
        return chunks
