from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agents import TravelPlanner
from .mcp_server import mcp as trip_mcp
from .models import TripPlan, TripRequest

# 构建一次 MCP streamable-http 子应用（惰性创建 session manager）
mcp_app = trip_mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动 MCP 的 StreamableHTTPSessionManager 任务组；
    # 不接线会报 "Task group is not initialized"，所有 /mcp 请求都会失败。
    async with trip_mcp.session_manager.run():
        yield


app = FastAPI(title="HelloAgents Trip Planner", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

planner = TravelPlanner()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---- 非流式接口（保留，向后兼容） ----
@app.post("/api/trip/plan", response_model=TripPlan)
def create_trip_plan(request: TripRequest) -> TripPlan:
    return planner.plan(request)


# ---- SSE 流式接口 ----
def _sse(event: str, payload) -> str:
    """把事件拼成 SSE 格式：event: 名称\ndata: JSON\n\n"""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/trip/plan/stream")
def stream_trip_plan(request: TripRequest) -> StreamingResponse:
    """逐阶段推送进度事件，最后推送完整结果。

    每个 Agent 运行几步之间插入一个 stage 事件，用户在前端能看到实时进度。
    用同步生成器：内部的 LLM 调用是阻塞的，交给线程池执行，避免卡住事件循环。
    """

    def event_stream():
        yield _sse("start", {"message": "开始规划行程..."})
        yield _sse("stage", {"stage": "research", "message": "正在语义检索目的地相关景点（RAG）..."})
        places = planner.researcher.run(request)
        yield _sse(
            "stage",
            {
                "stage": "itinerary",
                "message": f"已找到 {len(places)} 个候选景点，正在排行程（LLM 调用工具估算交通时间）...",
            },
        )
        day_plans = planner.itinerary.run(request, places)
        yield _sse("stage", {"stage": "budget", "message": "正在计算预算..."})
        budget = planner.budget.run(request, day_plans)
        plan = planner._assemble(request, places, day_plans, budget)
        yield _sse("result", plan.model_dump(mode="json"))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- MCP streamable-http 挂载 ----
app.mount("/mcp", mcp_app)
