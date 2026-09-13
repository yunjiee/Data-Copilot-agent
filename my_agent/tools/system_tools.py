import asyncio

async def wait_for_system_loading(seconds: int = 5) -> str:
    """
    當知識庫系統回報正在背景載入時，請呼叫此工具來暫停執行指定秒數。
    """
    await asyncio.sleep(seconds)
    return f"已成功等待 {seconds} 秒，系統可能已經準備好，請立刻重新呼叫檢索工具進行查詢。"