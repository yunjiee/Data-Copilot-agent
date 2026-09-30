import os

_CONTEXT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "context"
)


def _safe_context_path(name: str) -> str:
    """只取檔名部分並限定在 output/context 之下，避免「../」或絕對路徑穿越。"""
    safe_name = os.path.basename(name.strip().replace("\\", "/"))
    if not safe_name:
        raise ValueError("檔案名稱不可為空。")
    return os.path.join(_CONTEXT_DIR, safe_name)


def save_context_to_file(filename: str, content: str) -> str:
    """
    將分析結果或長篇內容儲存到指定檔案中，避免在多個 Agent 之間傳遞過長的上下文導致遺失。
    回傳儲存的檔案絕對路徑，請將此路徑提供給後續需要的 Agent（例如簡報製作 Agent）。
    
    Args:
        filename: 儲存的檔案名稱 (例如: analysis_result.md)
        content: 要儲存的完整內容 (例如: 數據分析結果或總結)
    """
    try:
        file_path = _safe_context_path(filename)
    except ValueError as e:
        return f"❌ 儲存失敗：{e}"
    os.makedirs(_CONTEXT_DIR, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"內容已成功儲存至：{file_path}"

def read_context_from_file(file_path: str) -> str:
    """
    讀取先前儲存的內容檔案，獲取完整的上下文資訊。當其他 Agent 提供檔案路徑給你時，請使用此工具讀取。
    只能讀取 save_context_to_file 儲存在 output/context 底下的檔案。
    
    Args:
        file_path: 要讀取的檔案路徑或檔名（只會取檔名部分）
    """
    try:
        safe_path = _safe_context_path(file_path)
    except ValueError as e:
        return f"❌ 讀取失敗：{e}"
    if not os.path.isfile(safe_path):
        return f"找不到檔案：{os.path.basename(safe_path)}"
    with open(safe_path, "r", encoding="utf-8") as f:
        return f.read()
