# Backend

Run the API:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Main endpoints:

```text
GET  /api/health               健康检查
POST /api/trip/plan            非流式完整行程
POST /api/trip/plan/stream      SSE 流式行程（逐阶段进度事件）
POST /mcp                       MCP streamable-http 端点（MCP 客户端连接地址）
```

## MCP

- 模块：`app/mcp_server.py`，暴露 5 个工具：`plan_trip` / `search_places` / `list_city_places` / `travel_minutes` / `travel_minutes_between_places`
- stdio 入口：`python -m app.mcp_server`（供 Claude Code / Claude Desktop 本地连接）
- HTTP 入口：`http://localhost:8000/mcp`（FastAPI 已挂载，需先启动 API）
- 调试：`npx @modelcontextprotocol/inspector`

## Docker

```bash
docker compose build   # 在项目根目录执行
docker compose up -d
```

The backend mirrors the chapter 13 project idea with three lightweight agents:

- `DestinationResearchAgent`: picks destination places.
- `ItineraryAgent`: arranges day-by-day itinerary.
- `BudgetAgent`: estimates cost.
