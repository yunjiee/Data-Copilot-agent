# rag_langchain_server：LangChain 版 RAG Server

和 `mcp_servers/rag_server`（手寫版）並存的第二個 RAG 實作。MCP Tool 介面完全相同，
Agent 以環境變數 `RAG_BACKEND` 切換要使用哪一版。

## 模組

| 檔案 | 職責 | 使用的 LangChain 元件 |
|---|---|---|
| `config.py` | 設定（環境變數前綴 `LC_RAG_`） | － |
| `loaders.py` | 讀取 .md / .txt，轉成 `Document` | `langchain_core.documents.Document` |
| `splitters.py` | 先依 Markdown 章節切，再依字數切 | `MarkdownHeaderTextSplitter`、`RecursiveCharacterTextSplitter` |
| `embeddings.py` | E5 模型，封裝 `query:` / `passage:` 前綴 | 繼承 `langchain_core.embeddings.Embeddings` |
| `vector_store.py` | 建庫與開啟 Qdrant | `langchain_qdrant.QdrantVectorStore` |
| `ingestion.py` | 離線建庫流程：load → split → embed → 寫入 | － |
| `retrieval_chain.py` | LCEL 檢索鏈：搜尋 → 格式化 | `RunnableLambda`、`as_retriever()` |
| `server.py` | FastMCP Server，Tool：`search_knowledge_base(query, top_k)` | － |

## 執行順序

```bash
# 0. 安裝依賴
uv sync

# 1. 檢查切塊（不需要載入模型）
uv run python scripts/RAG_langchain/test_splitter.py

# 2. 建庫（寫入 data/qdrant_langchain）
uv run python scripts/RAG_langchain/build_knowledge_base.py

# 3. 單題檢索測試
uv run python scripts/RAG_langchain/test_retrieval.py "退貨率要怎麼計算？"

# 4. 與原版比較（原版也要先建庫：scripts/RAG/build_knowledge_base.py）
uv run python scripts/eval/compare_retrievers.py

# 5. 讓 Agent 改用 LangChain 版
#    在 .env 加入 RAG_BACKEND=langchain，然後
uv run adk web . --reload --reload_agents
```

## 設定（.env，皆為選填）

| 變數 | 預設值 |
|---|---|
| `LC_RAG_COLLECTION_NAME` | `ecommerce_kb_langchain` |
| `LC_RAG_QDRANT_PATH` | `data/qdrant_langchain` |
| `LC_RAG_CHUNK_SIZE` / `LC_RAG_CHUNK_OVERLAP` | `500` / `100` |
| `LC_RAG_EMBEDDING_MODEL` | 沿用 `RAG_EMBEDDING_MODEL`，預設為 `intfloat/multilingual-e5-small` |

## 注意

- Qdrant Local Mode 同一個資料夾只能被一個程序開啟，所以兩版使用不同的資料夾。
- 兩版的 payload 格式不相容：原版是扁平的 `text` / `source` 欄位，LangChain 版是 `page_content` + `metadata`。因此兩版必須各自建庫。
