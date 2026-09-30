"""工具呼叫防護：輸入長度上限、每個對話的呼叫次數限制，以及稽核紀錄。

以 ADK 的 before_tool_callback / after_tool_callback 掛在每個 Agent 上，
所有工具（含 MCP 工具與 transfer_to_agent）都會經過這裡。
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from ..config import config

# --- 限制設定 ---------------------------------------------------------------

# 一般字串參數的長度上限；需要較長內容的工具在下方個別放寬
DEFAULT_ARG_LIMIT = 2000
ARG_LIMITS: dict[tuple[str, str], int] = {
    ("safe_write_pptx_script", "code_content"): 60_000,
    ("save_cache_data", "data"): 1_000_000,
    ("render_vegalite_chart", "spec"): 500_000,
    ("save_context_to_file", "content"): 200_000,
    ("execute_sql_query", "sql"): 4000,
    ("check_sql_syntax", "sql"): 4000,
}

# 每個對話（session）內所有工具的呼叫總數上限，以及個別工具的上限
MAX_CALLS_PER_SESSION = 80
TOOL_CALL_LIMITS: dict[str, int] = {
    "execute_sql_query": 15,
    "check_sql_syntax": 20,
    "get_daily_sales": 15,
    "get_product_performance": 15,
    "search_knowledge_base_guarded": 15,
    "search_knowledge_base": 15,
    "safe_execute_pptx_script": 5,
}

# --- 稽核紀錄 ---------------------------------------------------------------

_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"ya29\.[0-9A-Za-z_\-]+"),
    re.compile(r"sk-[0-9A-Za-z_\-]{16,}"),
    re.compile(r"Bearer\s+[0-9A-Za-z_\-\.=]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
]
_PREVIEW_CHARS = 200


def _build_audit_logger() -> logging.Logger:
    audit = logging.getLogger("audit")
    if audit.handlers:
        return audit
    log_dir = Path(config.mas_project_root) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "audit.jsonl", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit.addHandler(handler)
    audit.setLevel(logging.INFO)
    audit.propagate = False
    return audit


_audit = _build_audit_logger()
_lock = threading.Lock()
_call_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def _redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _preview(value: Any) -> str:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = repr(value)
    text = _redact(text)
    return text if len(text) <= _PREVIEW_CHARS else text[:_PREVIEW_CHARS] + f"...(共 {len(text)} 字元)"


def _arg_size(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return len(str(value))


def _session_key(ctx: Any) -> str:
    try:
        return str(ctx.session.id)
    except Exception:
        return "unknown-session"


def _write_audit(event: str, tool_name: str, ctx: Any, **extra: Any) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": event,
        "session": _session_key(ctx),
        "user": getattr(ctx, "user_id", None),
        "agent": getattr(ctx, "agent_name", None),
        "tool": tool_name,
        **extra,
    }
    _audit.info(json.dumps(record, ensure_ascii=False, default=str))


def _block(tool_name: str, ctx: Any, args: dict[str, Any], reason: str) -> dict[str, Any]:
    _write_audit("blocked", tool_name, ctx, reason=reason, args=_preview(args))
    _update_state(ctx, tool_name, "blocked", status="blocked")
    return {"status": "error", "error_message": f"🛑 [系統攔截] {reason}"}


# --- 對話狀態（ADK Web UI 的 State 頁籤）------------------------------------
# 僅供觀察：把執行概況寫進 session state，方便在 State 頁籤查看，不影響功能。

_MAX_LISTED_FILES = 20


def _update_state(ctx: Any, tool_name: str, event: str, status: Any = None, produced_files: Optional[list] = None) -> None:
    """更新 State 頁籤顯示的內容。任何錯誤都忽略，避免觀察功能影響主流程。"""
    try:
        state = ctx.state
        summary = dict(state.get("tool_summary") or {})
        summary["total_calls"] = int(summary.get("total_calls", 0)) + (1 if event == "call" else 0)
        summary["blocked"] = int(summary.get("blocked", 0)) + (1 if event == "blocked" else 0)
        per_tool = dict(summary.get("calls_by_tool") or {})
        if event == "call":
            per_tool[tool_name] = int(per_tool.get(tool_name, 0)) + 1
        summary["calls_by_tool"] = per_tool
        state["tool_summary"] = summary

        state["last_tool"] = {
            "tool": tool_name,
            "agent": getattr(ctx, "agent_name", None),
            "event": event,
            "status": status,
            "time": time.strftime("%H:%M:%S"),
        }
        if produced_files:
            files = list(state.get("saved_files") or [])
            files.extend(p for p in produced_files if p not in files)
            state["saved_files"] = files[-_MAX_LISTED_FILES:]
    except Exception:
        pass


# 產出檔案的 Windows 絕對路徑，到副檔名為止（不受工具回傳文字格式或全形標點影響）
_FILE_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\r\n\"'<>|?*]*?\.(?:pptx|js|png|json|md)", re.IGNORECASE)
_FILE_PRODUCING_TOOLS = {
    "save_cache_data", "render_vegalite_chart", "safe_write_pptx_script",
    "safe_execute_pptx_script", "save_context_to_file", "execute_sql_query",
}


def _extract_produced_files(tool_name: str, response: Any) -> list[str]:
    """從產生檔案的工具結果找出檔案路徑，找不到回傳空清單。"""
    if tool_name not in _FILE_PRODUCING_TOOLS:
        return []
    if isinstance(response, str):
        text = response
    elif isinstance(response, dict):
        text = str(response.get("cache_path") or response.get("result") or "")
    else:
        return []
    return list(dict.fromkeys(_FILE_PATH_RE.findall(text)))


def _result_status(response: Any) -> Optional[str]:
    """判斷工具結果狀態：dict 用 status 欄位（含 MCP 包裝），字串依開頭符號判斷。"""
    if isinstance(response, dict):
        if "status" in response:
            return str(response["status"])
        for item in response.get("content") or []:  # MCP 工具的結果包在 content[].text 裡
            try:
                inner = json.loads(item.get("text", ""))
                if isinstance(inner, dict) and "status" in inner:
                    return str(inner["status"])
            except Exception:
                continue
        return None
    if isinstance(response, str):
        if response.startswith(("❌", "🛑", "錯誤")):
            return "error"
        if response.startswith(("✅", "內容已成功")):
            return "success"
    return None


# --- ADK callbacks ----------------------------------------------------------

def before_tool_guard(tool: Any, args: dict[str, Any], tool_context: Any) -> Optional[dict[str, Any]]:
    """工具執行前：檢查輸入長度與呼叫次數；回傳 dict 代表攔截並直接當作工具結果。"""
    tool_name = getattr(tool, "name", str(tool))

    for arg_name, value in (args or {}).items():
        limit = ARG_LIMITS.get((tool_name, arg_name), DEFAULT_ARG_LIMIT)
        size = _arg_size(value)
        if size > limit:
            return _block(tool_name, tool_context, args,
                          f"參數 '{arg_name}' 長度 {size} 超過上限 {limit}，請縮短內容後再試。")

    session = _session_key(tool_context)
    with _lock:
        counts = _call_counts[session]
        counts["__total__"] += 1
        counts[tool_name] += 1
        total, per_tool = counts["__total__"], counts[tool_name]

    if total > MAX_CALLS_PER_SESSION:
        return _block(tool_name, tool_context, args,
                      f"本次對話的工具呼叫已達上限 ({MAX_CALLS_PER_SESSION} 次)，請停止呼叫工具並回報使用者。")
    tool_limit = TOOL_CALL_LIMITS.get(tool_name)
    if tool_limit is not None and per_tool > tool_limit:
        return _block(tool_name, tool_context, args,
                      f"工具 {tool_name} 在本次對話已達呼叫上限 ({tool_limit} 次)，請停止呼叫並回報使用者。")

    _write_audit("call", tool_name, tool_context, args=_preview(args))
    _update_state(tool_context, tool_name, "call")
    return None


def after_tool_guard(tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any) -> Optional[dict[str, Any]]:
    """工具執行後：記錄結果狀態與大小（不記錄完整內容），不修改回傳值。"""
    tool_name = getattr(tool, "name", str(tool))
    status = _result_status(tool_response)
    _write_audit("result", tool_name, tool_context, status=status,
                 size=_arg_size(tool_response), preview=_preview(tool_response))
    _update_state(tool_context, tool_name, "result", status=status,
                  produced_files=_extract_produced_files(tool_name, tool_response))
    return None
