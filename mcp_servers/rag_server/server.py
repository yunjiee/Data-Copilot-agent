from mcp.server.fastmcp import FastMCP
import logging
import os
import sys
import warnings
import threading

# 封殺 HuggingFace 與 Tokenizer 的進度條與警告，防止污染 MCP (Stdout) 通訊
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 忽略可能干擾 MCP 通訊的警告訊息
warnings.filterwarnings("ignore")
# 設定 Logging (會輸出到 stderr)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("rag_server")

# 1. 初始化 FastMCP 伺服器
mcp = FastMCP("RAG Knowledge Base Server")

# 2. 使用全域變數做延遲載入 (Lazy Loading)
_retrieval_service_instance = None
_model_loading_error = None
# 使用 Event 來控制「等待模型載入」的開關
model_ready = threading.Event()

# 新增：查詢快取機制，用來突破 MCP 的 5.0 秒執行超時限制
_query_cache = {}
_query_processing = set()

def _preload_models_in_background():
    """在背景預先載入 AI 模型，避免阻塞 MCP 啟動或工具呼叫"""
    global _retrieval_service_instance, _model_loading_error
    try:
        logger.info("[MCP] 背景任務：正在預先載入 Embedding 模型與 Qdrant...")
        from mcp_servers.rag_server.embedding_service import EmbeddingService
        from mcp_servers.rag_server.vector_store import QdrantVectorStore
        from mcp_servers.rag_server.retrieval_service import RetrievalService

        embedding_service = EmbeddingService()
        vector_store = QdrantVectorStore()
        _retrieval_service_instance = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        
        logger.info("[MCP] 背景任務：模型載入完成，正在進行第一次推論暖機 (Warm-up)...")
        # 偷偷在背景先算一次，把 PyTorch 冷啟動的 5 秒鐘消耗掉
        _retrieval_service_instance.retrieve(query="暖機測試", top_k=1)
        
        logger.info("[MCP] 背景任務：暖機完成！知識庫系統 100% 準備就緒。")
    except Exception as e:
        _model_loading_error = str(e)
        logger.error(f"[MCP] 模型背景載入失敗: {e}")
    finally:
        # 無論成功或失敗，都把鎖解開，讓等待中的請求可以繼續往下走
        model_ready.set()

# 3. 註冊為 MCP Tool
@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 3) -> str:
    """
    當使用者詢問公司內部規定、專業知識、業務流程等問題時，請呼叫此工具來檢索內部知識庫。
    
    Args:
        query: 使用者的自然語言問題 (越詳細越好)。
        top_k: 要檢索的資料筆數，預設為 3 筆。
    """
    logger.info(f"[MCP Tool] 收到檢索請求：{query} (top_k={top_k})")
    
    # 為了避開 ADK 嚴格的 5 秒 Client 超時，若模型尚未就緒，立即回報狀態絕不傻等
    if not model_ready.is_set():
        return "⚠️ 系統正在背景載入知識庫模型，請稍後重新查詢。"

    # 如果載入其實失敗了
    if _model_loading_error is not None:
        raise RuntimeError(f"知識庫模型載入失敗: {_model_loading_error}")

    # 滿足 IDE 型別檢查，並提供最後一層執行時期防護
    if _retrieval_service_instance is None:
        return "⚠️ 系統發生預期外的錯誤，知識庫服務尚未成功實例化。"
        
    service = _retrieval_service_instance

    # ---------------------------------------------------------
    # 突破 5.0 秒運算限制：將檢索轉為背景非同步執行 (Job Queue 模式)
    # ---------------------------------------------------------
    cache_key = f"{query}_{top_k}"
    
    if cache_key in _query_cache:
        # 背景運算已完成，直接秒回結果！
        return _query_cache[cache_key]
        
    if cache_key in _query_processing:
        # 還在算，請 Agent 繼續等
        return "⚠️ 系統正在背景載入與計算檢索中，請稍後重新查詢。"

    # 第一次收到此問題，啟動背景運算
    _query_processing.add(cache_key)
    
    def _background_search():
        try:
            _query_cache[cache_key] = service.retrieve(query=query, top_k=top_k)
        except Exception as e:
            _query_cache[cache_key] = f"檢索發生錯誤: {e}"
        finally:
            _query_processing.discard(cache_key) # 計算結束後，清除處理中標記
            
    threading.Thread(target=_background_search, daemon=True).start()
    
    return "⚠️ 系統正在背景載入與計算檢索中，請稍後重新查詢。"


def main():
    """啟動 MCP 伺服器"""
    logger.info("[MCP] 啟動 RAG Knowledge Base MCP Server...")
    # 伺服器一啟動，就立刻在背景悄悄載入模型
    threading.Thread(target=_preload_models_in_background, daemon=True).start()
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()