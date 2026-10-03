"""search_knowledge_base_guarded 的重試與逾時處理回歸測試。

不啟動真正的 MCP server，也不載入整個 agent：以假的 rag_mcp_toolset 取代。
執行：uv run --no-sync pytest tests/test_knowledge_tools.py
"""
import importlib
import sys
import types

import pytest

LOADING_REPLY = "⚠️ 系統正在背景載入知識庫模型，請稍後重新查詢。"


class FakeTool:
    """依序回傳預先設定好的結果，並記錄被呼叫幾次。"""

    name = "search_knowledge_base"

    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = 0

    async def run_async(self, **kwargs):
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return reply


class FakeToolset:
    def __init__(self, tool):
        self._tool = tool

    async def get_tools(self):
        return [self._tool]


@pytest.fixture
def guarded(monkeypatch):
    """回傳 (search_knowledge_base_guarded, 安裝假工具的函式)。"""
    fake_agent = types.ModuleType("my_agent.agent")
    fake_agent.root_agent = None
    monkeypatch.setitem(sys.modules, "my_agent.agent", fake_agent)
    module = importlib.import_module("my_agent.tools.knowledge_tools")

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)  # 測試時不真的等 5 秒

    def install(replies):
        tool = FakeTool(replies)
        fake_agent.rag_mcp_toolset = FakeToolset(tool)
        return tool

    return module.search_knowledge_base_guarded, install


@pytest.mark.asyncio
async def test_returns_immediately_when_ready(guarded):
    search, install = guarded
    tool = install(["退貨率 = 退貨數 / 訂單數"])

    result = await search("退貨率")

    assert result["status"] == "success"
    assert tool.calls == 1


@pytest.mark.asyncio
async def test_retries_until_ready(guarded):
    search, install = guarded
    tool = install([LOADING_REPLY, LOADING_REPLY, "查詢結果"])

    result = await search("退貨率")

    assert result == {"status": "success", "result": "查詢結果"}
    assert tool.calls == 3


@pytest.mark.asyncio
async def test_loading_timeout_gives_clear_instruction(guarded):
    search, install = guarded
    tool = install([LOADING_REPLY])  # 永遠載入中

    result = await search("退貨率")

    assert tool.calls == 6  # 用完重試次數
    assert result["status"] == "loading_timeout"
    assert "result" not in result  # 不把後端原始訊息交給模型
    assert "不要再重試" in result["error_message"]


@pytest.mark.asyncio
async def test_content_containing_word_loading_is_not_treated_as_loading(guarded):
    """回歸：知識庫內容剛好出現英文 loading 時，不可被誤判為載入中而重試。"""
    search, install = guarded
    content = "Data loading 流程：先載入原始資料，再做清洗。"
    tool = install([content])

    result = await search("資料載入流程")

    assert result == {"status": "success", "result": content}
    assert tool.calls == 1


@pytest.mark.asyncio
async def test_missing_tool_returns_error(guarded, monkeypatch):
    search, _ = guarded
    sys.modules["my_agent.agent"].rag_mcp_toolset = FakeToolset(
        types.SimpleNamespace(name="other_tool")
    )

    result = await search("退貨率")

    assert result["status"] == "error"
