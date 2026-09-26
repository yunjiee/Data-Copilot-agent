import os
import subprocess
from typing import List, Dict, Any

# --- 強制防護機制：記錄 Agent 嘗試執行腳本失敗的次數 ---
MAX_PPTX_RETRIES = 3
MAX_TOTAL_EXECUTIONS = 5
_pptx_retry_count = 0
_total_execution_count = 0

def reset_pptx_execution_state() -> str:
    """重設 PPT 腳本執行的重試與計數器狀態（開始新的簡報製作任務時可調用）。"""
    global _pptx_retry_count, _total_execution_count
    _pptx_retry_count = 0
    _total_execution_count = 0
    return "✅ PPTX 執行狀態與計數器已重設。"

def analyze_reference_pptx(reference_filename: str) -> str:
    """
    當使用者有提供參考範例簡報時，請呼叫此工具。
    此工具會透過 `pptx/scripts` 資料夾中的解析工具，讀取參考簡報的架構、版型與樣式，
    並回傳解析後的 JSON 或結構資訊，供你模仿其設計並替換成新簡報的內容。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 假設簡報檔案放在 output 資料夾中或上傳到指定目錄
    output_dir = os.path.join(project_root, "output")
    scripts_dir = os.path.join(project_root, "my_agent", "skills", "pptx", "pptx", "scripts")
    
    safe_filename = os.path.basename(reference_filename)
    file_path = os.path.join(output_dir, safe_filename)
    
    if not os.path.exists(file_path):
        return f"❌ 錯誤：找不到參考簡報檔案 {safe_filename}。請確認檔名或確認檔案是否已放置於 {output_dir}。"
    
    parse_script = os.path.join(scripts_dir, "extract_structure.js") # 請確認對應提取的腳本名稱
    if not os.path.exists(parse_script):
        return f"⚠️ 警告：找不到解析腳本 {parse_script}。請依照您原本對該簡報的認知與設計規範來進行模仿，或向使用者要求提供更詳細的結構描述。"
    
    try:
        result = subprocess.run(["node", parse_script, file_path], capture_output=True, text=True, timeout=30, cwd=scripts_dir)
        if result.returncode == 0:
            return f"✅ 參考簡報架構解析成功！以下為提取的結構資訊：\n{result.stdout}\n\n請將此結構版型應用於您要生成的新簡報程式碼中。"
        else:
            return f"❌ 參考簡報解析失敗，錯誤訊息：\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "❌ 錯誤：參考簡報解析超時 (超過 30 秒)。"
    except Exception as e:
        return f"❌ 發生未預期的系統錯誤：{str(e)}"

def safe_write_pptx_script(filename: str, code_content: str) -> str:
    """
    [安全防護版] 當 Agent 根據手冊寫好產生 PPT 的 Node.js 程式碼後，呼叫此工具存檔。
    請提供檔名 (例如: make_deck.js) 與完整的程式碼。
    系統將會在寫入後執行語法檢查，避免不必要的執行錯誤與空轉。
    """
    global _pptx_retry_count, _total_execution_count
    if _pptx_retry_count >= MAX_PPTX_RETRIES:
        return "🛑 [系統強制攔截] 您已達最大失敗重試次數 (3次)。系統已鎖定寫入權限，請立即「停止嘗試」，並直接向使用者回報無法產生簡報。"

    # 1. 安全防護：使用 basename 防止目錄穿越攻擊 (Directory Traversal, 例如傳入 ../../windows/system32/...)
    safe_filename = os.path.basename(filename)
    if not safe_filename.endswith('.js'):
        return "❌ 錯誤：基於安全考量，只能寫入 .js 檔案。"
        
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    file_path = os.path.join(output_dir, safe_filename)
    
    # 2. 安全防護：簡單的危險關鍵字過濾
    forbidden_keywords = ['child_process', 'exec', 'spawn', 'fs.unlink', 'fs.rm']
    for kw in forbidden_keywords:
        if kw in code_content:
            return f"❌ 錯誤：程式碼包含被禁止的危險關鍵字 ({kw})，不允許執行系統指令或刪除檔案。請修正您的程式碼。"
            
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code_content)
        
    # 3. 強制防護機制：寫入後立即進行 Node.js 語法檢查，提前攔截低級錯誤
    try:
        check_result = subprocess.run(["node", "-c", safe_filename], capture_output=True, text=True, cwd=output_dir)
        if check_result.returncode != 0:
            return f"❌ 錯誤：程式碼存在語法錯誤 (Syntax Error)，請立即修正後再重新寫入：\n{check_result.stderr}"
    except Exception as e:
        return f"⚠️ 語法檢查發生異常，但檔案已寫入：{str(e)}"

    return f"✅ 檔案已成功安全寫入至：{file_path}。現在你可以呼叫 safe_execute_pptx_script 來執行它。"

def safe_execute_pptx_script(filename: str) -> str:
    """
    [安全防護版] 執行已存檔的 PPT 生成腳本。
    """
    global _pptx_retry_count, _total_execution_count
    
    if _total_execution_count >= MAX_TOTAL_EXECUTIONS:
        return f"🛑 [系統強制攔截] 您已達總執行次數上限 ({MAX_TOTAL_EXECUTIONS}次)。為避免無限空轉浪費資源，請立即「停止嘗試」，直接向使用者回報任務失敗。"

    if _pptx_retry_count >= MAX_PPTX_RETRIES:
        return "🛑 [系統強制攔截] 您已達最大失敗重試次數 (3次)。系統已鎖定執行權限，請立即「停止嘗試」，並直接向使用者回報無法產生簡報。"

    safe_filename = os.path.basename(filename)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(project_root, "output")
    reports_dir = os.path.join(project_root, "mas_output", "reports")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    file_path = os.path.join(output_dir, safe_filename)
    
    if not os.path.exists(file_path):
        return f"❌ 錯誤：找不到檔案 {safe_filename}。請先使用 write 工具生成檔案。"
        
    try:
        _total_execution_count += 1
        # 4. 安全防護：限制只執行 Node.js，且加上 Timeout 防止無窮迴圈浪費運算資源
        result = subprocess.run(["node", safe_filename], capture_output=True, text=True, timeout=30, cwd=output_dir)
        if result.returncode == 0:
            _pptx_retry_count = 0  # 執行成功，將計數器歸零
            return f"✅ 腳本執行成功！輸出：\n{result.stdout}"
        else:
            _pptx_retry_count += 1
            if _pptx_retry_count >= MAX_PPTX_RETRIES:
                return f"❌ 腳本執行失敗。錯誤訊息：\n{result.stderr}\n\n🛑 [系統強制攔截] 這是您的第 {_pptx_retry_count} 次失敗，已達重試上限！請立即停止呼叫工具嘗試修復，直接向使用者回報任務失敗。"
            return f"❌ 腳本執行失敗。錯誤訊息：\n{result.stderr}\n請檢查並修正腳本後再試一次 (剩餘重試次數: {MAX_PPTX_RETRIES - _pptx_retry_count})。"
    except subprocess.TimeoutExpired:
        _pptx_retry_count += 1
        return f"❌ 錯誤：腳本執行超時 (超過 30 秒被強制中斷)。可能存在無窮迴圈或等待輸入，請修改程式碼 (剩餘重試次數: {MAX_PPTX_RETRIES - _pptx_retry_count})。"
    except Exception as e:
        _pptx_retry_count += 1
        return f"❌ 發生未預期的系統錯誤：{str(e)} (剩餘重試次數: {MAX_PPTX_RETRIES - _pptx_retry_count})"
