"""MCP 服务端回归测试：工具注册齐全 + plan_trip 必须异步（防事件循环冻结）。"""
import asyncio

from app.mcp_server import mcp

EXPECTED_TOOLS = {
    "plan_trip",
    "search_places",
    "list_city_places",
    "travel_minutes",
    "travel_minutes_between_places",
}


def test_mcp_registers_exactly_five_tools():
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS


def test_plan_trip_is_async():
    # 回归保护：plan_trip 内部调用阻塞的 DeepSeek，必须 async + to_thread，
    # 否则 FastMCP 会把同步工具直接挂在事件循环上，冻结所有 MCP 会话。
    from app.mcp_server import plan_trip

    assert asyncio.iscoroutinefunction(plan_trip)


def test_plan_trip_has_expected_params():
    import inspect

    from app.mcp_server import plan_trip

    sig = inspect.signature(plan_trip)
    params = list(sig.parameters)
    assert params[:2] == ["destination", "days"]
    assert "people" in params and "budget_level" in params and "travel_style" in params
    assert "interests" in params and "notes" in params
