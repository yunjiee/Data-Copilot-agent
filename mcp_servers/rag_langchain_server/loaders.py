"""mcp_servers/rag_langchain_server/loaders.py

讀取知識庫資料夾中的 .md / .txt 文件，轉成 LangChain 的 Document。

說明：
不使用 LangChain 的 DirectoryLoader，因為它預設依賴 unstructured 套件
（體積大、安裝容易失敗）。這裡自己用 pathlib 讀檔，
輸出的仍是標準的 langchain_core.documents.Document，後續元件都能直接使用。
"""

from pathlib import Path

from langchain_core.documents import Document

SUPPORTED_SUFFIXES = {".md", ".txt"}


def scan_documents(source_dir: Path) -> list[Path]:
    """掃描資料夾內所有支援格式的文件，依檔名排序。"""
    if not source_dir.exists():
        raise FileNotFoundError(f"知識庫資料夾不存在：{source_dir}")

    if not source_dir.is_dir():
        raise NotADirectoryError(f"知識庫路徑不是資料夾：{source_dir}")

    return sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def load_documents(source_dir: Path) -> list[Document]:
    """
    將資料夾內的文件讀成 Document 清單。

    每份 Document 的 metadata 帶有：
    - source：檔案名稱（與原版 payload 的 source 欄位一致，方便比較）
    """
    documents: list[Document] = []

    for file_path in scan_documents(source_dir):
        try:
            text = file_path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError(f"文件不是 UTF-8 編碼：{file_path}") from exc

        if not text:
            print(f"略過空白文件：{file_path.name}")
            continue

        documents.append(
            Document(
                page_content=text,
                metadata={"source": file_path.name},
            )
        )

    return documents
