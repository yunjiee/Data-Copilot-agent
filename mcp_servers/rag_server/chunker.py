from dataclasses import dataclass

from mcp_servers.rag_server.config import (
    RagSettings,
    rag_settings,
)


@dataclass(frozen=True)
class DocumentChunk:
    """代表切割後的一個文件片段。"""

    chunk_index: int
    text: str
    source: str
    start_char: int
    end_char: int


class TextChunker:
    """依照固定字元數切割文字。"""

    def __init__(
        self,
        settings: RagSettings = rag_settings,
    ) -> None:
        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap

    def _get_current_heading(self, text: str, current_pos: int) -> str:
        """往回找尋最近的 Markdown 標題"""
        # 包含當前位置的開頭一點點，往回尋找
        text_before = text[:current_pos + 1]
        lines = text_before.split("\n")
        for line in reversed(lines):
            line = line.strip()
            # 確保是真正的 Markdown 標題 (例如 "# 標題" 或 "## 標題")
            if line.startswith("#") and " " in line:
                return line.lstrip("#").strip()
        return "未指定章節"

    def build_chunk_text(self, source: str, heading: str, content: str) -> str:
        """將來源、標題與內容組合，提升 AI 檢索與理解上下文的能力"""
        return (
            f"文件：{source}\n"
            f"章節：{heading}\n"
            f"內容：\n{content.strip()}"
        )

    def split_text(
        self,
        text: str,
        source: str = "unknown",
    ) -> list[DocumentChunk]:
        """
        將一份完整文字切割成多個重疊片段。

        Args:
            text:
                要切割的完整文件內容。

            source:
                文件來源，例如檔案名稱。

        Returns:
            切割完成的 DocumentChunk 清單。
        """
        cleaned_text = text.strip()

        if not cleaned_text:
            return []

        step = self.chunk_size - self.chunk_overlap

        chunks: list[DocumentChunk] = []
        start_char = 0
        chunk_index = 0

        while start_char < len(cleaned_text):
            end_char = min(
                start_char + self.chunk_size,
                len(cleaned_text),
            )

            chunk_text = cleaned_text[
                start_char:end_char
            ].strip()

            if chunk_text:
                # 動態抓取這個片段所屬的章節標題
                heading = self._get_current_heading(cleaned_text, start_char)
                
                # 將片段「加料」包裝
                enriched_text = self.build_chunk_text(
                    source=source, heading=heading, content=chunk_text
                )

                chunks.append(
                    DocumentChunk(
                        chunk_index=chunk_index,
                        text=enriched_text,
                        source=source,
                        start_char=start_char,
                        end_char=end_char,
                    )
                )

            # 已經到達文件最後，就結束迴圈
            if end_char >= len(cleaned_text):
                break

            start_char += step
            chunk_index += 1

        return chunks