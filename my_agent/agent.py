import os
import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
)
from .tools.calculation_tools import (
    calculate_growth_rate,
)
from .tools.system_tools import wait_for_system_loading
from mcp import StdioServerParameters
from .config import config
from .prompts import (
    ROOT_AGENT_INSTRUCTION,
    ANALYTICS_AGENT_INSTRUCTION,
    KNOWLEDGE_AGENT_INSTRUCTION,
)
import logging

# agent.py 位於 my-adk-project/my_agent/agent.py
# parents[1] 就是 my-adk-project
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# MCP Server 子程序使用的環境變數
server_environment = os.environ.copy()

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
    ),

    # 只將這兩個 MCP Tool 提供給 Agent
    tool_filter=[
        "get_daily_sales",
        "get_server_status",
        "get_product_performance",
    ],
)

# 建立 RAG 使用的 MCP Client／Toolset
rag_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            # 假設你的 RAG 伺服器啟動檔在 mcp_servers.rag_server.server
            args=[
                "-m",
                "mcp_servers.rag_server.server",
            ],
            cwd=str(PROJECT_ROOT),
            env=server_environment,
        ),
    ),
    tool_filter=["search_knowledge_base"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

# 建立專門處理數據的子 Agent
analytics_agent = LlmAgent(
    name="analytics_agent",
    model=config.worker_model,
    description="數據分析專家，負責處理 BigQuery SQL 查詢，取得營收、訂單與商品績效等量化數據。",
    instruction=ANALYTICS_AGENT_INSTRUCTION,
    tools=[analytics_mcp_toolset],
)

# 建立專門處理知識庫的子 Agent
knowledge_agent = LlmAgent(
    name="knowledge_agent",
    model=config.worker_model,
    description="知識庫專家，負責檢索公司內部政策、規定、文件與流程說明等質化資訊。",
    instruction=KNOWLEDGE_AGENT_INSTRUCTION,
    tools=[rag_mcp_toolset, wait_for_system_loading],
)

# 總管 Agent (負責與使用者溝通並派發任務)
root_agent = LlmAgent(
    name="coordinator_agent",
    model=config.worker_model,
    description=(
        "TheLook eCommerce 總管 Agent，負責分析問題並分派給對應的專業子 Agent。"
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[
        AgentTool(agent=analytics_agent),
        AgentTool(agent=knowledge_agent),
        calculate_growth_rate,
    ],
    include_contents="default", # Agent 可以取得相關對話歷史
)