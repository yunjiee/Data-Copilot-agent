from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# RAG server 在模型尚未就緒時回傳的固定句子（兩個 server 都包含此字串）
LOADING_MARKER = "正在背景載入"


async def search_knowledge_base_guarded(
    query: str,
    top_k: int = 5,
    tool_context: Any = None,
) -> dict[str, Any]:
    """檢索公司內部知識庫與規範，內建 Python 底層自動輪詢與重試機制。

    若後端系統正在背景載入或冷啟動，Python 會在底層自動進行非同步等待並重試，
    最長容忍 35 秒，無需透過 Agent 處理等待輪次。

    Args:
        query: 檢索的關鍵字或自然語言問題。
        top_k: 檢索返回的段落數量，預設為 5。
        tool_context: ADK 工具執行環境上下文。
    """
    max_retries = 8
    retry_delay_seconds = 5

    for attempt in range(1, max_retries + 1):
        logger.info("執行知識庫檢索 (嘗試 %d/%d): query=%s", attempt, max_retries, query)
        
        # 呼叫底層 MCP 工具 search_knowledge_base
        from ..agent import rag_mcp_toolset
        tools = await rag_mcp_toolset.get_tools()
        target_tool = next((t for t in tools if getattr(t, "name", None) == "search_knowledge_base"), None)

        if not target_tool:
            return {
                "status": "error",
                "error_message": "找不到底層 RAG 工具 search_knowledge_base，請確認 MCP 伺服器狀態。",
            }

        if hasattr(target_tool, "run_async"):
            kwargs: dict[str, Any] = {"args": {"query": query, "top_k": top_k}}
            if tool_context is not None:
                kwargs["tool_context"] = tool_context
            raw_result = await target_tool.run_async(**kwargs)
        else:
            raw_result = await target_tool(query=query, top_k=top_k)
        
        result_str = str(raw_result)
        
        # 檢查後端是否仍處於背景加載或冷啟動狀態
        is_loading = LOADING_MARKER in result_str
        if is_loading and attempt < max_retries:
            logger.info(
                "知識庫系統載入中，Python 正在進行背景非同步等待 %d 秒後重試 (累計等待 %d 秒)...",
                retry_delay_seconds,
                attempt * retry_delay_seconds,
            )
            await asyncio.sleep(retry_delay_seconds)
            continue

        return {
            "status": "success" if not is_loading else "loading_timeout",
            "result": raw_result,
        }