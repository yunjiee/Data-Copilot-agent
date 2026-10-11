import os
import sys
from pathlib import Path

from google.adk.agents import ( 
    LlmAgent,
)
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
)

from .tools.calculation_tools import (
    calculate_growth_rate,
)
from .tools.knowledge_tools import search_knowledge_base_guarded
from .tools.pptx_tools import (
    analyze_reference_pptx,
    safe_write_pptx_script,
    safe_execute_pptx_script,
    reset_pptx_execution_state,
)
from .tools.cache_tools import (
    save_cache_data,
    load_cache_data,
    list_cache_files,
)

from .tools.chart_tools import render_vegalite_chart
from .tools.skill_toolset import SkillToolset
from .tools.guard import before_tool_guard, after_tool_guard
from mcp import StdioServerParameters
from .config import config
from .prompts import (
    ROOT_AGENT_INSTRUCTION,
    ANALYTICS_AGENT_INSTRUCTION,
    KNOWLEDGE_AGENT_INSTRUCTION,
    REPORT_AGENT_INSTRUCTION,
)
import logging

# agent.py 位於 my-adk-project/my_agent/agent.py
# parents[1] 就是 my-adk-project
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# MCP Server 子程序使用的環境變數：只傳必要變數，避免 GOOGLE_API_KEY 等機敏資訊被帶進子程序。
# （MCP 另外會補上 PATH、SYSTEMROOT、USERPROFILE、APPDATA 等基本系統變數）
_ENV_ALLOW_EXACT = {
    "PATH", "PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING", "VIRTUAL_ENV",
    "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
    "HOME", "MAXIMUM_BYTES_BILLED", "GOOGLE_APPLICATION_CREDENTIALS",
}
_ENV_ALLOW_PREFIXES = (
    "BIGQUERY_", "RAG_", "LC_RAG_", "GOOGLE_CLOUD_", "CLOUDSDK_",
    "HF_", "TRANSFORMERS_", "SENTENCE_TRANSFORMERS_", "TOKENIZERS_",
)
server_environment = {
    key: value
    for key, value in os.environ.items()
    if key.upper() in _ENV_ALLOW_EXACT or key.upper().startswith(_ENV_ALLOW_PREFIXES)
}

# 讓 MCP Server 能找到專案根目錄下的 mcp_servers package
existing_pythonpath = server_environment.get(
    "PYTHONPATH",
    "",
)

server_environment["PYTHONPATH"] = os.pathsep.join(
    path
    for path in [
        str(PROJECT_ROOT),
        existing_pythonpath,
    ]
    if path
)


# 只給模型使用的 Analytics MCP Tool。
# reset_sql_fix_state 是「停損鎖」的解鎖開關，不能讓模型自己呼叫（否則等於可以繞過重試上限），
# 因此不在這份名單中，只由程式在每輪對話開始時呼叫（見 _reset_sql_fix_state）。
ANALYTICS_MODEL_TOOLS = frozenset(
    {
        "check_sql_syntax",
        "execute_sql_query",
        "get_daily_sales",
        "get_server_status",
        "get_product_performance",
        "get_query_context",
    }
)
_INTERNAL_RESET_TOOL = "reset_sql_fix_state"


class _InternalContext(ReadonlyContext):
    """標記「這是程式內部在取工具」的 context；模型取得工具清單時不會用到它。"""


def _analytics_tool_filter(tool, readonly_context=None) -> bool:
    if tool.name in ANALYTICS_MODEL_TOOLS:
        return True
    return tool.name == _INTERNAL_RESET_TOOL and isinstance(
        readonly_context, _InternalContext
    )


# 建立 ADK 使用的 MCP Client／Toolset
analytics_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            # 使用目前 uv 虛擬環境的 Python
            command=sys.executable,

            # 等同執行：
            # python -m mcp_servers.analytics_data_server.server
            args=[
                "-m",
                "mcp_servers.analytics_data_server.server",
            ],

            # MCP Server 子程序的工作目錄
            cwd=str(PROJECT_ROOT),

            # 把目前環境變數傳入 MCP Server
            env=server_environment,
        ),
        timeout=config.mcp_startup_timeout,
    ),

    # 只將 ANALYTICS_MODEL_TOOLS 提供給模型（含 Text-to-SQL 的驗證、Dry Run 與執行）
    tool_filter=_analytics_tool_filter,
)

# 根據環境變數 RAG_BACKEND 動態決定啟動哪一個 RAG MCP Server
rag_server_module = (
    "mcp_servers.rag_langchain_server.server"
    if os.getenv("RAG_BACKEND", "").strip().lower() == "langchain"
    else "mcp_servers.rag_server.server"
)

# 建立 RAG 使用的 MCP Client／Toolset
rag_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                rag_server_module,
            ],
            cwd=str(PROJECT_ROOT),
            env=server_environment,
        ),
        timeout=config.mcp_startup_timeout,
    ),
    tool_filter=["search_knowledge_base"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

async def _reset_sql_fix_state(callback_context):
    """每次進入 analytics_agent（新一輪提問）時，由程式重設 SQL 修正計數器。

    失敗只記錄警告，不中斷對話；計數器在查詢成功後本來就會自動歸零。
    """
    try:
        internal_context = _InternalContext(callback_context._invocation_context)
        tools = await analytics_mcp_toolset.get_tools(internal_context)
        reset_tool = next(t for t in tools if t.name == _INTERNAL_RESET_TOOL)
        await reset_tool.run_async(args={}, tool_context=callback_context)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "重設 SQL 修正計數器失敗，沿用目前計數。", exc_info=True
        )
    return None


# 建立專門處理數據的子 Agent
analytics_agent = LlmAgent(
    name="analytics_agent",
    model=config.worker_model,
    description="數據分析專家 (Producer)，負責處理 BigQuery SQL 查詢，取得營收、訂單與商品績效等量化數據並存入快取。",
    instruction=ANALYTICS_AGENT_INSTRUCTION,
    before_agent_callback=_reset_sql_fix_state,
    before_tool_callback=before_tool_guard,
    after_tool_callback=after_tool_guard,
    tools=[
        analytics_mcp_toolset,
        save_cache_data,
    ],
)

# 建立專門處理知識庫的子 Agent
knowledge_agent = LlmAgent(
    name="knowledge_agent",
    model=config.worker_model,
    description="知識庫專家 (Producer)，負責檢索公司內部政策、規定、文件與流程說明等質化資訊並存入快取。",
    instruction=KNOWLEDGE_AGENT_INSTRUCTION,
    before_tool_callback=before_tool_guard,
    after_tool_callback=after_tool_guard,
    tools=[
        search_knowledge_base_guarded,
        save_cache_data,
    ],
)

# 建立 Report 專用的 SkillToolset (同時整合洞察手冊與 PPTX 規範)
pptx_skills_dir = PROJECT_ROOT / "my_agent" / "skills" / "pptx"
if (pptx_skills_dir / "pptx" / "SKILL.md").exists():
    pptx_skills_dir = pptx_skills_dir / "pptx"

report_skill_toolset = SkillToolset(
    skills_dir=pptx_skills_dir,
    skills=[
        "insight_generation_skill.md",  # 洞察提煉框架 (透過 SkillResolver fallback 讀取)
        "SKILL.md",                     # 簡報排版與主題配色手冊
        "pptxgenjs.md",                # PptxGenJS 程式語法規範
    ],
)

# 建立專門處理商業洞察與簡報製作的單一 Report Agent (Consumer)
report_agent = LlmAgent(
    name="report_agent",
    model=config.worker_model,
    description="商業洞察與簡報製作專家 (Consumer)，負責整合快取中的量化數據與質化知識，提煉洞察並直接產製 PowerPoint 簡報與圖表。",
    instruction=REPORT_AGENT_INSTRUCTION,
    before_tool_callback=before_tool_guard,
    after_tool_callback=after_tool_guard,
    tools=[
        report_skill_toolset,
        load_cache_data,
        save_cache_data,
        render_vegalite_chart,
        safe_write_pptx_script,
        safe_execute_pptx_script,
        reset_pptx_execution_state,
        analyze_reference_pptx,
    ],
)

# 總管 Agent (Selector 角色，負責解析意圖與分派任務)
root_agent = LlmAgent(
    name="coordinator_agent",
    model=config.worker_model,
    description=(
        "TheLook eCommerce 總管 Agent (Selector)，負責分析問題、檢查快取狀態並分派給專業子 Agent。"
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    before_tool_callback=before_tool_guard,
    after_tool_callback=after_tool_guard,
    sub_agents=[
        analytics_agent,
        knowledge_agent,
        report_agent,
    ],
    tools=[
        calculate_growth_rate,
        list_cache_files,
    ],
    include_contents="default", # Agent 可以取得相關對話歷史
)