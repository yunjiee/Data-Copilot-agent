import os

def save_context_to_file(filename: str, content: str) -> str:
    """
    將分析結果或長篇內容儲存到指定檔案中，避免在多個 Agent 之間傳遞過長的上下文導致遺失。
    回傳儲存的檔案絕對路徑，請將此路徑提供給後續需要的 Agent（例如簡報製作 Agent）。
    
    Args:
        filename: 儲存的檔案名稱 (例如: analysis_result.md)
        content: 要儲存的完整內容 (例如: 數據分析結果或總結)
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "output", "context")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"內容已成功儲存至：{file_path}"

def read_context_from_file(file_path: str) -> str:
    """
    讀取先前儲存的內容檔案，獲取完整的上下文資訊。當其他 Agent 提供檔案路徑給你時，請使用此工具讀取。
    
    Args:
        file_path: 要讀取的檔案絕對路徑
    """
    if not os.path.exists(file_path):
        return f"找不到檔案：{file_path}"
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()