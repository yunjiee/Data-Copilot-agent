"""mcp_servers/rag_langchain_server/server.py

LangChain 版 RAG 的 FastMCP Server。

設計重點：
- Tool 名稱與參數與原版完全相同：search_knowledge_base(query, top_k)。
  Agent 端（knowledge_tools.py 的重試機制、prompts）不需要任何修改，
  只要在 agent.py 以 RAG_BACKEND 切換啟動哪一個 Server。
- 沿用原版的「背景預先載入 + 背景查詢快取」機制。
  這是為了處理 ADK MCP Client 約 5 秒的逾時限制，與 LangChain 無關，
  換成 LangChain 後這個問題依然存在，所以必須保留。
- 回傳的「正在背景載入」字串與原版一致，
  knowledge_tools.search_knowledge_base_guarded 才能辨識並自動重試。
"""

import logging
import os
import sys
import threading
import warnings

from mcp.server.fastmcp import FastMCP

# 關閉 HuggingFace 與 Tokenizer 的進度條與警告，避免污染 MCP (stdout) 通訊
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("rag_langchain_server")

mcp = FastMCP("RAG Knowledge Base Server (LangChain)")

_retrieval_service = None
_model_loading_error: str | None = None
model_ready = threading.Event()

_query_cache: dict[str, str] = {}
_query_processing: set[str] = set()

LOADING_MESSAGE = (
    "⚠️ 系統正在背景載入與計算檢索中，請稍後重新查詢。"
)


def _preload_in_background() -> None:
    """背景載入 Embedding 模型與 Qdrant，並暖機一次。"""
    global _retrieval_service, _model_loading_error
    try:
        logger.info("[MCP-LC] 背景任務：正在載入 E5Embeddings 與 QdrantVectorStore...")
        from mcp_servers.rag_langchain_server.embeddings import E5Embeddings
        from mcp_servers.rag_langchain_server.retrieval_chain import (
            LangChainRetrievalService,
        )
        from mcp_servers.rag_langchain_server.vector_store import open_vector_store

        embedding = E5Embeddings()
        vector_store = open_vector_store(embedding=embedding)
        _retrieval_service = LangChainRetrievalService(vector_store=vector_store)

        logger.info("[MCP-LC] 背景任務：載入完成，進行暖機推論...")
        _retrieval_service.retrieve(query="暖機測試", top_k=1)
        logger.info("[MCP-LC] 背景任務：暖機完成，知識庫已就緒。")
    except Exception as e:
        _model_loading_error = str(e)
        logger.error(f"[MCP-LC] 背景載入失敗: {e}")
    finally:
        model_ready.set()


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 3) -> str:
    """
    當使用者詢問公司內部規定、專業知識、業務流程等問題時，請呼叫此工具來檢索內部知識庫。

    Args:
        query: 使用者的自然語言問題 (越詳細越好)。
        top_k: 要檢索的資料筆數，預設為 3 筆。
    """
    logger.info(f"[MCP-LC Tool] 收到檢索請求：{query} (top_k={top_k})")

    if not model_ready.is_set():
        return LOADING_MESSAGE

    if _model_loading_error is not None:
        raise RuntimeError(f"知識庫模型載入失敗: {_model_loading_error}")

    if _retrieval_service is None:
        return "⚠️ 系統發生預期外的錯誤，知識庫服務尚未成功實例化。"

    service = _retrieval_service
    cache_key = f"{query}_{top_k}"

    if cache_key in _query_cache:
        return _query_cache[cache_key]

    if cache_key in _query_processing:
        return LOADING_MESSAGE

    _query_processing.add(cache_key)

    def _background_search() -> None:
        try:
            _query_cache[cache_key] = service.retrieve(query=query, top_k=top_k)
        except Exception as e:
            _query_cache[cache_key] = f"檢索發生錯誤: {e}"
        finally:
            _query_processing.discard(cache_key)

    threading.Thread(target=_background_search, daemon=True).start()
    return LOADING_MESSAGE


def main() -> None:
    logger.info("[MCP-LC] 啟動 RAG Knowledge Base MCP Server (LangChain)...")
    threading.Thread(target=_preload_in_background, daemon=True).start()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
