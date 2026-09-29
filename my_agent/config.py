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

@dataclass
class AgentConfiguration:
    """Configuration for MAS Phase 1 Agent.

    Attributes:
        critic_model (str): Model for SQL evaluation and quality review.
        worker_model (str): Model for schema generation and tool building.
        max_sql_fix_iterations (int): Maximum SQL fix loop iterations.
        mas_project_root (str): Root path for generated output and cache files.
    """

    critic_model: str = "gemini-3.1-pro-preview"
    worker_model: str = "gemini-3.1-pro-preview"
    distiller_model: str = "gemini-3-flash-preview"
    max_sql_fix_iterations: int = 3
    mas_project_root: str = os.getenv("MAS_PROJECT_ROOT", "./mas_output")


config = AgentConfiguration()
