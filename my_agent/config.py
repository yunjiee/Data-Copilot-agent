import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file in the project root directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Authentication Configuration:
# By default, uses AI Studio with GOOGLE_API_KEY from .env file.
# To use Vertex AI instead, set GOOGLE_GENAI_USE_VERTEXAI=TRUE in your .env
# and ensure you have Google Cloud credentials configured.

if os.getenv("GOOGLE_API_KEY"):
    # AI Studio mode (default): Use API key authentication
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")
else:
    # Vertex AI mode: Fall back to Google Cloud credentials
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id"))
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
    import google.auth
    google.auth.default()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_root(value: str) -> str:
    """相對路徑以專案根目錄為基準轉成絕對路徑，與 MCP Server 的解析方式一致。"""
    path = Path(value)
    return str(path if path.is_absolute() else PROJECT_ROOT / path)


@dataclass
class AgentConfiguration:
    """MAS Agent 設定。值一律來自 .env，程式碼中的字串只是 .env 缺漏時的備援預設值。

    Attributes:
        worker_model (str): WORKER_MODEL，各 Agent 執行用模型。
        mas_project_root (str): MAS_PROJECT_ROOT，輸出與快取根目錄（絕對路徑）。
        mcp_startup_timeout (float): MCP_STARTUP_TIMEOUT，等待 MCP Server 啟動的秒數。
    """

    worker_model: str = os.getenv("WORKER_MODEL", "gemini-3.1-pro-preview")
    mas_project_root: str = _resolve_root(os.getenv("MAS_PROJECT_ROOT", "./mas_output"))
    # 等待 MCP Server 子程序啟動完成的秒數（ADK 預設 5 秒，冷啟動 import bigquery 常超過）
    mcp_startup_timeout: float = float(os.getenv("MCP_STARTUP_TIMEOUT", "60"))


config = AgentConfiguration()
