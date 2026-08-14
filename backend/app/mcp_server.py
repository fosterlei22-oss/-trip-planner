"""MCP 服务端：把旅行助手的核心能力暴露成 MCP 工具。

支持两种传输方式：
- stdio：`python -m app.mcp_server`（本地，供 Claude Desktop / Claude Code 使用）
- streamable-http：由 main.py 挂载到 FastAPI 的 /mcp（远程 / Docker 内访问）

暴露 5 个工具：
- plan_trip                   多 Agent 完整行程规划（RAG → 编排 → 工具调用 → 预算）
- search_places                RAG 语义检索景点
- list_city_places             查询城市景点知识库
- travel_minutes               按坐标估算市内交通时间
- travel_minutes_between_places 按景点名估算交通时间
"""
from __future__ import annotations

import asyncio
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .agents import TravelPlanner
from .data import CITY_PLACES, DEFAULT_PLACES
from .models import TripRequest
from .rag import retrieve
from .tools import travel_minutes as _travel_minutes

# streamable_http_path="/" + 挂载在 /mcp 时，端点正好是 /mcp（否则会变成 /mcp/mcp）。
# host="0.0.0.0" 关闭 FastMCP 默认的 localhost-only DNS-rebinding/origin 白名单，
# 否则 Docker 内部（Host 头是 backend:8000）或局域网客户端的请求会被拦截。
mcp = FastMCP(
    "trip-planner",
    instructions="智能旅行规划助手：生成完整行程、查询景点知识库、估算市内交通时间。",
    streamable_http_path="/",
    host="0.0.0.0",
)

# 与 main.py 的模块级 planner 分离，避免循环导入（两者无状态、创建开销极小）
_planner = TravelPlanner()


def _do_plan(
    destination: str,
    days: int,
    people: int,
    budget_level: str,
    travel_style: str,
    interests: list[str] | None,
    notes: str,
) -> dict:
    request = TripRequest(
        destination=destination,
        days=days,
        people=people,
        budget_level=budget_level,
        travel_style=travel_style,
        interests=interests or [],
        notes=notes or "",
    )
    return _planner.plan(request).model_dump(mode="json")


@mcp.tool()
async def plan_trip(
    destination: str,
    days: int,
    people: int = 2,
    budget_level: Literal["economy", "standard", "comfort"] = "standard",
    travel_style: Literal["relaxed", "classic", "deep", "family", "foodie"] = "classic",
    interests: list[str] | None = None,
    notes: str = "",
) -> dict:
    """为指定目的地生成一份完整旅行计划（每日行程、预算拆分、路线点、打包清单、贴士）。

    内部会调用 DeepSeek（RAG 检索 + 多 Agent 编排 + 工具调用），可能耗时 10~60 秒。
    未配置 DEEPSEEK_API_KEY 时会自动降级为规则引擎生成，保证可用。
    """
    # 同步实现放进线程池执行：FastMCP 对同步工具是直接挂在事件循环上跑的，
    # 而这里内部有阻塞的 LLM 调用，会冻结整个事件循环（卡死所有 MCP 会话）。
    return await asyncio.to_thread(
        _do_plan, destination, days, people, budget_level, travel_style, interests, notes
    )


@mcp.tool()
def search_places(city: str, interests: list[str] | None = None, top_k: int = 5) -> dict:
    """用 RAG 语义检索返回与兴趣最匹配的景点列表。"""
    query = f"{city}旅行 兴趣：{'、'.join(interests or [])}"
    names = retrieve(query, city=city, top_k=top_k)
    by_name = {p.name: p for p in (CITY_PLACES.get(city) or DEFAULT_PLACES)}
    places = [by_name[n].model_dump(mode="json") for n in names if n in by_name]
    return {"places": places, "count": len(places)}


@mcp.tool()
def list_city_places(city: str) -> dict:
    """返回某城市知识库中的全部景点（北京/上海/杭州/成都）。"""
    places = CITY_PLACES.get(city)
    if not places:
        raise ValueError(f"未知城市：{city}，可用城市：{'、'.join(CITY_PLACES)}")
    items = [p.model_dump(mode="json") for p in places]
    return {"places": items, "count": len(items)}


@mcp.tool()
def travel_minutes(
    lat1: float, lng1: float, lat2: float, lng2: float, speed_kmh: float = 24.0
) -> int:
    """估算两个坐标点之间的市内交通时间（分钟）。"""
    return _travel_minutes(lat1, lng1, lat2, lng2, speed_kmh)


@mcp.tool()
def travel_minutes_between_places(city: str, place_a: str, place_b: str) -> int:
    """按景点名估算城市内两个景点之间的交通时间（分钟）。"""
    by_name = {p.name: p for p in (CITY_PLACES.get(city) or DEFAULT_PLACES)}
    a, b = by_name.get(place_a), by_name.get(place_b)
    if a is None or b is None:
        raise ValueError(f"未知景点：{place_a} / {place_b}")
    return _travel_minutes(a.lat, a.lng, b.lat, b.lng)


if __name__ == "__main__":
    # stdio 传输：供 Claude Desktop / Claude Code 以本地进程方式调用
    mcp.run(transport="stdio")
