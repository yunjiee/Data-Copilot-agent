# TheLook 智慧電商助理 (SSOT Agent)

基於 **Google Agent Development Kit (ADK)** 與 **Gemini** 構建的智能代理系統。
本專案無縫整合了量化數據分析與質化知識檢索，旨在為企業提供單一真相來源 (SSOT, Single Source of Truth) 的全方位問答體驗。

## ✨ 核心功能 (Core Features)

本專案透過總管 Agent (Coordinator) 負責意圖識別，並動態分派任務給對應的專業 Agent，具備以下三大核心能力：

### 1. 📊 MCP 聯動 BigQuery 數據分析 (Analytics Agent)
透過 **MCP (Model Context Protocol)** 標準，Agent 能夠與 Google BigQuery 深度連動，達成自動化的數據探查。
- **Text-to-SQL**：將使用者的自然語言問題轉化為精確的 BigQuery Standard SQL 查詢。
- **動態執行與反思**：自動執行 SQL 撈取營收、訂單與商品績效等量化數據；若遇到語法錯誤，Agent 能自主反思並修正 SQL。

### 2. 📚 RAG 向量知識庫檢索 (Knowledge Agent)
同樣基於 **MCP (Model Context Protocol)** 協定串接專屬的 RAG 伺服器，並整合向量資料庫 (Vector DB)，精準回答內部規範與指標定義。
- **核心工具 (Tools)**：Agent 可自主判斷並呼叫 `search_knowledge_base` 工具執行檢索。
- **語意比對 (Semantic Search)**：將使用者問題轉換為向量，快速從內部文件中檢索出最相關的段落。
- **精確溯源**：回覆時標註資料來源（如 `ecommerce_metric_definitions.md`），確保知識的正確性（例如嚴格區分「商品退貨率」與「訂單退貨率」）。

### 3. 📈 自動化商業簡報生成 (Report Pipeline)
整合數據洞察與規範定義，透過流水線依序由 `insight_agent` 與 `presentation_agent` 產出高品質投影片：
- **商業洞察提煉**：自動歸納關鍵營運指標並規劃投影片大綱架構。
- **圖表渲染與生成**：使用 Vega-Lite 渲染高解析視覺化圖表，並呼叫 PptxGenJS (Node.js) 自動排版輸出 PPTX 檔案。
- **快取循環機制**：支援本地快取 (`mas_output/cache/`)，避免重複查詢資料庫，大幅加速簡報生成與調優。

---

## 🛠️ 開發前準備 (Prerequisites)

請確保您的環境已安裝以下工具：

| 工具 | 版本要求 | 說明 |
|------|----------|------|
| **Python** | >= 3.11 | 核心語言環境（由 `uv` 依 `pyproject.toml` 管理） |
| **Node.js** | >= 18 | 執行 PPTX 生成腳本 (PptxGenJS) |
| **uv** | 最新版 | Python 套件與虛擬環境管理 |
| **Google Cloud SDK** | 最新版 | 用於 ADC 憑證授權（BigQuery 與 Vertex AI） |

### 安裝 `uv`

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## 📥 安裝步驟 (Installation)

### 1. 進入專案目錄

```bash
cd Data-Copilot-agent
```

### 2. 安裝 Python 依賴項

`uv` 會自動建立虛擬環境 `.venv` 並安裝 `pyproject.toml` 中定義的所有套件（包含 `google-adk`）：

```bash
uv sync
```

### 3. 安裝 Node.js 依賴項

簡報生成使用 PptxGenJS：

```bash
npm install
```

### 4. 建立 `.env`

在**專案根目錄**建立 `.env`（已被 `.gitignore` 排除，請勿提交到版本控制，也不要把內容貼到對話或 Issue 中）。範例：

```dotenv
# --- Gemini 驗證（二擇一）---
# 方式 A：AI Studio。設定後即使用 API Key
GOOGLE_API_KEY=your-api-key
# 方式 B：Vertex AI。不設定 GOOGLE_API_KEY 時，改用 ADC 與下列專案
GOOGLE_CLOUD_PROJECT=your-gcp-project-id

# --- BigQuery（必填）---
BIGQUERY_PROJECT=your-billing-project-id          # 建立查詢工作並計費的專案
BIGQUERY_DATA_PROJECT=bigquery-public-data        # 資料所在專案
BIGQUERY_DATASET=thelook_ecommerce                # 資料集

# --- 選填 ---
BIGQUERY_LOCATION=US                              # 預設 US
MAXIMUM_BYTES_BILLED=104857600                    # 單次查詢計費上限，預設 100 MiB
RAG_BACKEND=native                                # 設為 langchain 改用 LangChain 版 RAG
MAS_PROJECT_ROOT=./mas_output                     # 輸出與快取根目錄
```

RAG 相關變數（`RAG_*`、`LC_RAG_*`）請參考 [`mcp_servers/rag_server/README.md`](mcp_servers/rag_server/README.md) 與 [`mcp_servers/rag_langchain_server/README.md`](mcp_servers/rag_langchain_server/README.md)。

### 5. 建立知識庫向量索引

首次使用前，需先把 `data/knowledge_base/` 下的文件寫入本機 Qdrant：

```bash
# 預設（原生版 RAG）
uv run python scripts/RAG/build_knowledge_base.py

# 若 RAG_BACKEND=langchain
uv run python scripts/RAG_langchain/build_knowledge_base.py
```

---

## ⚙️ GCP 憑證授權 (Authentication)

本專案使用 **ADC（Application Default Credentials）** 存取 BigQuery，未設定 `GOOGLE_API_KEY` 時也以 ADC 呼叫 Vertex AI 上的 Gemini。

### Step 1：取得 ADC

```bash
gcloud auth application-default login --disable-quota-project
```

瀏覽器會開啟 Google 帳號登入頁，請選擇對您 `.env` 中指定的專案**具備存取權限的帳號**。

> **`--disable-quota-project` 的用途**：加上此旗標後，ADC 憑證檔案中不會寫入 `quota_project_id`，
> 避免配額或計費意外算在其他舊有專案上。實際計費專案由 `.env` 的 `BIGQUERY_PROJECT`（BigQuery）與 `GOOGLE_CLOUD_PROJECT`（Vertex AI）決定。

### Step 2：確認憑證已正確取得

```bash
gcloud auth application-default print-access-token
```

成功時會輸出一組 token 字串，表示 ADC 已就緒。**此 token 屬於敏感資訊，請勿分享或貼到公開處。**

### Step 3：確認帳號的 IAM 權限

| 服務 | 必要角色 | 授予專案 |
|------|---------|----------|
| **Vertex AI（Gemini 呼叫，僅方式 B 需要）** | `roles/aiplatform.user` | `GOOGLE_CLOUD_PROJECT` |
| **BigQuery（資料探查）** | `roles/bigquery.jobUser` | `BIGQUERY_PROJECT` |
| **BigQuery（讀取資料）** | `roles/bigquery.dataViewer` | `BIGQUERY_DATA_PROJECT`（公開資料集通常已可讀取） |

---

## 🚀 啟動 Agent（本地開發測試）

在專案根目錄使用以下命令啟動 ADK 內建 Web UI（**推薦加入 `--reload` 與 `--reload_agents` 以開啟自動熱重載與代理人動態載入**）：

```bash
uv run adk web . --reload --reload_agents
```

啟動後，在瀏覽器開啟：

```
http://localhost:8000
```

即可看到 ADK Web UI，選取 `my_agent` 並開始對話測試。

---

## 🔒 安全防護 (Security)

Agent 內建以下防護，避免被誘導越權：

| 位置 | 防護內容 |
|------|----------|
| `my_agent/tools/skill_toolset.py` | `read_skill` 只取檔名並限白名單，擋下 `../`、絕對路徑；不對 Agent 開放建立技能 |
| `my_agent/tools/sql_tools.py` | 僅允許唯讀查詢，且資料表限定在 `BIGQUERY_DATA_PROJECT.BIGQUERY_DATASET.*`；另有除零保護與 100 MiB 掃描量上限 |
| `my_agent/prompts.py` | 總管限定服務範圍，超出範圍直接拒絕；禁止輸出金鑰、環境變數與系統檔案內容 |

---

## 🧩 Agent 設定調整 (Customization)

主要設定集中於以下檔案：

| 檔案 | 說明 |
|------|------|
| [`my_agent/config.py`](my_agent/config.py) | Gemini 驗證方式、模型、最大修正次數、輸出路徑等核心參數 |
| [`my_agent/agent.py`](my_agent/agent.py) | Agent 的主要邏輯、子 Agent 與 MCP 伺服器定義 |
| [`my_agent/prompts.py`](my_agent/prompts.py) | 各階段的 Prompt 模板 |
| [`my_agent/tools/`](my_agent/tools) | Agent 可呼叫的工具（SQL、快取、圖表、PPTX、知識檢索、技能） |
| [`mcp_servers/`](mcp_servers) | Analytics 與 RAG 的 MCP 伺服器 |
| `.env`（專案根目錄） | API Key、GCP 專案等敏感環境變數，不會提交到 Git |

### 調整模型（`my_agent/config.py`）

```python
@dataclass
class AgentConfiguration:
    critic_model: str = "gemini-3.1-pro-preview"    # 評估與審查用模型
    worker_model: str = "gemini-3.1-pro-preview"    # 工作執行用模型
    distiller_model: str = "gemini-3-flash-preview" # 資料提煉用模型
    max_sql_fix_iterations: int = 3                 # SQL 最大修正迭代次數
    mas_project_root: str = os.getenv("MAS_PROJECT_ROOT", "./mas_output")  # 輸出根目錄
```

## 🔧 常見問題排查 (Troubleshooting)

| 問題 | 解決方式 |
|------|----------|
| `uv: command not found` | 重新安裝 `uv` 並確認已加入 PATH |
| `python: command not found`（Windows 出現 Microsoft Store 提示） | 系統 PATH 沒有 Python，請改用 `uv run python ...` |
| 啟動時 pydantic 報缺少 `BIGQUERY_*` 欄位 | 確認專案根目錄的 `.env` 已設定 `BIGQUERY_PROJECT`、`BIGQUERY_DATA_PROJECT`、`BIGQUERY_DATASET` |
| Vertex AI 認證失敗 | 執行 `gcloud auth application-default login --disable-quota-project` 重新取得憑證 |
| 模型或 BigQuery 回傳 403 | 確認帳號在對應專案具備上表的 IAM 角色 |
| SQL 被回報「只能查詢 ... 底下的資料表」 | 查詢的資料表不在 `BIGQUERY_DATA_PROJECT.BIGQUERY_DATASET` 之下，屬預期的安全攔截 |
| 知識庫檢索查無資料 | 尚未建立索引，請執行「建立知識庫向量索引」步驟；Qdrant 本地模式同一時間僅允許一個程序開啟 |
| Agent 啟動後頁面空白 | 確認 `my_agent/__init__.py` 有正確匯出 `root_agent` |

---

## 📚 相關資源

- [ADK 官方文件](https://google.github.io/adk-docs/)
- [Vertex AI 認證說明](https://cloud.google.com/vertex-ai/docs/authentication)
- [Agent Starter Pack](https://googlecloudplatform.github.io/agent-starter-pack/)
