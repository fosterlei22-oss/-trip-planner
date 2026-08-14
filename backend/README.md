# Backend

Run the API:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Run tests (无 API key 也能全绿，走降级路径):

```bash
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -v
```

Main endpoints:

```text
GET  /api/health               健康检查
GET  /api/metrics              可观测性：请求/LLM/工具计数、阶段耗时 p50/p95、降级次数、缓存命中率
POST /api/trip/plan            非流式完整行程
POST /api/trip/plan/stream      SSE 流式行程（逐阶段进度事件，自动合并会话记忆）
POST /mcp                       MCP streamable-http 端点（MCP 客户端连接地址）
```

### 缓存与记忆（可选，自动降级）

不配置也能全功能运行——KV 后端默认进程内内存、零网络；配置了 `REDIS_URL` 才连 Redis，
连不上自动回退内存（`/api/metrics` 的 `cache.backend` 可见）。

```bash
# .env 可选
REDIS_URL=redis://localhost:6379
```

### 评估套件（Agent Evaluation）

15 个 golden case × 不变式校验（天数/互异性/防幻觉/预算恒等式），cold → warm 双遍量化缓存收益：

```bash
python -m eval.run_eval               # 规则引擎轨（无 key，CI 安全、秒级）
python -m eval.run_eval --with-llm    # 真实 DeepSeek 轨
python -m eval.run_eval --json        # 机器可读输出
python -m eval.run_eval --cases 5     # 只跑前 5 个用例
```

规则引擎轨实测：pass_rate **15/15 = 100%**、hallucination_rate **0.0**、
RAG 缓存命中 cold 0% → warm **100%**、平均耗时 0.5ms → 0.1ms（-80%）。

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
