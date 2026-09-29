# rag_server：原生實作版 RAG Knowledge Base Server

本模組為自研原生 Python 實作的內部知識庫檢索服務。使用原生切塊器、E5 模型前綴封裝與 Qdrant Client 打造，透過 FastMCP 提供標準化的 Knowledge Retrieval Tool，供 Agent 進行質化規範檢索。

## 核心架構與職責

1. **Knowledge Ingestion & Indexing (`chunker.py`, `vector_store.py`)**：
   - 讀取內部營運與業務文件（`.md` / `.txt`）。
   - 使用自定義滑動窗口切塊（`TextChunker`）維護段落重疊。
   - 呼叫 `intfloat/multilingual-e5-small` 進行向量化，並寫入本機 Qdrant 向量資料庫（`data/qdrant`）。
2. **Retriever Validation (`retrieval_service.py`)**：
   - 封裝 E5 模型的查詢前綴（`query: ` 與 `passage: `）。
   - 支援基於 Cosine 相似度的向量檢索與 Top-K 候選段落組裝。
3. **FastMCP Integration (`server.py`)**：
   - 封裝為 MCP 工具 `search_knowledge_base(query, top_k)`。
   - 內建背景載入與 Warm-up 暖機機制，並支援非同步查詢快取（Job Queue 模式）以突破 MCP Client 5 秒逾時限制。
4. **Retrieval Evaluation (`eval/`)**：
   - 透過標準固定評測題集，量化評估原生檢索品質。
   - 核心量化指標包含：Recall@K、MRR（Mean Reciprocal Rank）與來源正確率。

## 執行與驗證步驟

```bash
# 1. 安裝環境依賴
uv sync

# 2. 原生向量資料庫建庫（寫入 data/qdrant）
uv run python scripts/RAG/build_knowledge_base.py

# 3. 獨立檢索驗證
uv run python scripts/RAG/test_retrieval.py "退貨率要怎麼計算？"

# 4. 檢索品質指標評估（固定題集測試 Recall@K、MRR 與命中率）
uv run python scripts/eval/compare_retrievers.py

# 5. 啟動 MCP 伺服器（獨立測試或調試用）
uv run python mcp_servers/rag_server/server.py
```

## 環境設定（`.env`）

| 環境變數 | 預設值 | 說明 |
|---|---|---|
| `RAG_COLLECTION_NAME` | `ecommerce_internal_knowledge` | Qdrant 集合名稱 |
| `RAG_QDRANT_PATH` | `data/qdrant` | 本機 Qdrant 資料持久化目錄 |
| `RAG_SOURCE_DIR` | `data/knowledge_base` | 原始知識文件放置目錄 |
| `RAG_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | 向量模型名稱 |
| `RAG_CHUNK_SIZE` | `500` | 切塊字元數大小 |
| `RAG_CHUNK_OVERLAP` | `100` | 切塊重疊字元數 |
| `RAG_TOP_K` | `5` | 預設檢索返回筆數（範圍 1~20） |
| `RAG_EMBEDDING_BATCH_SIZE` | `16` | 批次 Embedding 大小 |

## 注意事項

- **Qdrant 本地鎖定**：Qdrant Local 模式在同一時間只允許一個程序打開資料庫檔案。若要同時對比原生版與 LangChain 版，兩者需指向不同目錄（`data/qdrant` 與 `data/qdrant_langchain`）。
- **Payload 結構差異**：原生版採用扁平欄位（`text`, `source`, `chunk_index`, `start_char`, `end_char`），與 LangChain 版（`page_content` + `metadata`）不共用，需各自執行建庫腳本。