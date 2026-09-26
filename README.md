# TheLook 智慧電商助理 (SSOT Agent)

基於 **Google Agent Development Kit (ADK)** 與 **Gemini** 構建的智能代理系統。
本專案無縫整合了量化數據分析與質化知識檢索，旨在為企業提供單一真相來源 (SSOT, Single Source of Truth) 的全方位問答體驗。

## ✨ 核心功能 (Core Features)

本專案透過總管 Agent (Coordinator) 負責意圖識別，並動態分派任務給對應的專業 Agent，具備以下三大核心能力：

### 1. 📊 MCP 聯動 BigQuery 數據分析 (Analytics Agent)
透過 **MCP (Model Context Protocol)** 標準，Agent 能夠與 Google BigQuery 深度連動，達成自動化的數據探查。
- **Text-to-SQL**：將使用者的自然語言問題轉化為精確的 BigQuery Legacy/Standard SQL 查詢。
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
| **Python** | 3.10 ~ 3.12 | 核心語言環境 |
| **Node.js** | >= 18 | 執行 PPTX 生成腳本 (PptxGenJS) |
| **uv** | 最新版 | Python 套件與虛擬環境管理 |
| **Google Cloud SDK** | 最新版 | 用於 Vertex AI 帳戶授權 |

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

### 2. 安裝所有 Python 依賴項

`uv` 會自動建立虛擬環境 `.venv` 並安裝 `pyproject.toml` 中定義的所有套件（包含 `google-adk`）：

```bash
uv sync
```

---

## ⚙️ GCP 憑證授權 (Authentication)

本專案統一使用 **Vertex AI** 作為 Gemini 模型的呼叫方式，並透過 **BigQuery** 執行資料探查。  
所有 GCP 資源皆固定使用專案 `ddd-gemini-enterprise`，已在程式碼中硬設，**無需修改任何 `.env`**。

### Step 1：取得 ADC（Application Default Credentials）

執行以下命令完成本地憑證授權：
只負責建立「身分憑證」，且不把 quota project 寫進 ADC。

```bash
gcloud auth application-default login --disable-quota-project
```

瀏覽器會開啟 Google 帳號登入頁，選擇對 `ddd-gemini-enterprise` **具備存取權限的帳號**完成授權。

> **`--disable-quota-project` 的用途**：
> 加上此旗標後，ADC 憑證檔案中不會寫入 `quota_project_id` 欄位。
> 這可以避免 API 呼叫時意外將配額或計費算在舊有的其他專案（如 `ddd-model-gap`）上，
> 確保所有費用完全由程式碼中明確指定的 `ddd-gemini-enterprise` 承擔。

> **⚠️ 關於 ADC 的 quota project**
>
> 若您的 ADC 預設 quota project 是其他專案（例如 `ddd-model-gap`），**不影響本專案的運作**。
> 原因如下：
>
> | 項目 | 由誰決定 | 本專案設定 |
> |------|---------|-----------|
> | **您的身份（帳號）** | ADC 登入的 Google 帳號 | 需有 `ddd-gemini-enterprise` 權限 |
> | **Vertex AI 使用專案** | `GOOGLE_CLOUD_PROJECT` 環境變數 | 程式碼已固定為 `ddd-gemini-enterprise` |
> | **BigQuery 計費專案** | `bigquery.Client(project=...)` | 程式碼已固定為 `ddd-gemini-enterprise` |
> | **ADC 的 quota_project** | `gcloud auth application-default login` 時帶入 | ✅ 使用 `--disable-quota-project` 清空，避免意外計費 |

### Step 2：確認憑證已正確取得

```bash
gcloud auth application-default print-access-token
```

成功時會輸出一組 token 字串，表示 ADC 已就緒。

### Step 3：確認帳號對 `ddd-gemini-enterprise` 的存取權限

帳號至少需要以下 IAM 權限才能正常運作：

| 服務 | 必要角色 |
|------|---------|
| **Vertex AI（Gemini 呼叫）** | `roles/aiplatform.user` |
| **BigQuery（資料探查）** | `roles/bigquery.dataViewer` + `roles/bigquery.jobUser` |

---

## 🚀 啟動 Agent（本地開發測試）

確認已進入 `my-deep-search-agent` 目錄後，使用以下命令啟動 ADK 內建 Web UI（**推薦加入 `--reload` 與 `--reload_agents` 以開啟自動熱重載與代理人動態載入！**）：

```bash
uv run adk web . --reload --reload_agents
```

啟動後，在瀏覽器開啟：

```
http://localhost:8000
```

即可看到 ADK Web UI，選取 Agent 並開始對話測試。


## 🧩 Agent 設定調整 (Customization)

主要設定集中於以下檔案：

| 檔案 | 說明 |
|------|------|
| [`my_agent/config.py`](my_agent/config.py) | Agent 使用的 Gemini 模型、最大迭代次數、輸出路徑等核心參數 |
| [`my_agent/agent.py`](my_agent/agent.py) | Agent 的主要邏輯與子 Agent 定義 |
| [`my_agent/prompts.py`](my_agent/prompts.py) | 各階段的 Prompt 模板 |
| [`my_agent/tools.py`](my_agent/tools.py) | Agent 可呼叫的工具函式（如 Web 搜尋） |
| `my_agent/.env` | API Key / GCP 專案等敏感環境變數 |

### 調整模型（`my_agent/config.py`）

```python
@dataclass
class MASConfiguration:
    critic_model: str = "gemini-3.1-pro-preview"  # 評估與審查用模型
    worker_model: str = "gemini-3.1-pro-preview"  # 工作執行用模型
    max_sql_fix_iterations: int = 3               # 最大修正迭代次數
    mas_project_root: str = "./mas_output"        # 輸出根目錄
```

## 🔧 常見問題排查 (Troubleshooting)

| 問題 | 解決方式 |
|------|----------|
| `uv: command not found` | 重新安裝 `uv` 並確認已加入 PATH |
| Vertex AI 認證失敗 | 執行 `gcloud auth application-default login` 重新取得憑證 |
| 模型呼叫回傳 403 | 確認 GCP 帳號對 `ddd-gemini-enterprise` 專案有 Vertex AI 使用權限 |
| Agent 啟動後頁面空白 | 確認 `my_agent/__init__.py` 有正確匯出 Agent 物件 |

---

## 📚 相關資源

- [ADK 官方文件](https://google.github.io/adk-docs/)
- [Vertex AI 認證說明](https://cloud.google.com/vertex-ai/docs/authentication)
- [Agent Starter Pack](https://googlecloudplatform.github.io/agent-starter-pack/)
