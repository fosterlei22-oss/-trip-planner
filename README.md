# 🧭 智能旅行助手 · LLM 多 Agent 应用

一个从零实现的 **LLM 多 Agent 应用**：输入目的地、天数、预算、兴趣，系统通过「RAG 语义检索 → 多 Agent 编排 → 工具调用 → SSE 流式输出」实时生成完整旅行计划（每日行程、预算拆分、路线图、打包清单）。

后端 FastAPI + Pydantic，前端 Vue 3 + TypeScript。研究、行程两个 Agent 由 DeepSeek 驱动，预算 Agent 保持确定性计算，形成「**LLM 决策 + 代码执行**」的异构多 Agent 架构。

> **🔥 本仓库的增量（教程之外的原创工程化）**
>
> 本项目基于 DataWhale「Hello Agents」教程的多 Agent 骨架，但在其之上**额外实现**了以下面试官会追问的差异化能力：
> - **MCP 服务端**：5 个工具，stdio + streamable-http 双传输（教程没有，官方 SDK 从零接入）
> - **Docker 全栈容器化** + nginx 反向代理（SSE 流式适配、API key 不进镜像）
> - **pytest 冒烟测试 + GitHub Actions CI**（含 LLM 降级路径，无 key 也能全绿）
> - **Render 云端部署蓝图**：免费一键上线，简历可直接挂 URL
> - **会话记忆**：`session_id` 多轮偏好保持，响应回显「已记住你的偏好」
> - **Redis 缓存 + 优雅降级**：RAG/LLM 双层缓存，连不上自动回退内存，带命中率度量
> - **可观测性**：`GET /api/metrics`——阶段耗时 p50/p95、LLM/工具计数、降级次数
> - **Agent 评估套件**：15 golden case × 不变式校验 → 通过率 / 幻觉率 / cold-warm 缓存收益

## ✨ 核心能力

| 能力 | 说明 |
|---|---|
| **多 Agent 编排** | `TravelPlanner` 按数据依赖串联 研究 → 行程 → 预算，每层职责单一、可独立替换 |
| **RAG 语义检索** | 40 个景点向量化入库，按用户需求语义召回 top-k，再交 LLM 精排（粗筛/细选两阶段） |
| **Function Calling** | ReAct 工具循环：LLM 决定调用 `travel_minutes` 工具（Haversine 计算真实交通时间），代码执行、结果回喂 |
| **JSON Mode** | 强制 LLM 输出结构化 JSON，Pydantic 二次校验，非法结果自动降级 |
| **SSE 流式输出** | 逐阶段推送进度事件（text/event-stream），前端 fetch 读流实时显示 |
| **优雅降级** | 每一层都有兜底：RAG 失败 → 本地数据，LLM 失败 → 规则引擎，系统永不宕 |
| **防幻觉** | LLM 只允许从候选列表选择，返回名字与真实数据核对，校验失败整层降级 |

## 🏗 架构

```
用户请求
  │  POST /api/trip/plan/stream (SSE)
  ▼
TravelPlanner（编排器）
  ├─► DestinationResearchAgent
  │     ├─ RAG：向量库语义召回 top-k（粗筛）
  │     └─ LLM：JSON mode 排序去噪（精排）
  ├─► ItineraryAgent
  │     ├─ LLM + Function Calling（travel_minutes 工具）
  │     └─ Haversine 公式计算真实交通时间，就近安排、同天不重复
  ├─► BudgetAgent
  │     └─ 确定性代码计算（住宿 / 餐饮 / 交通 / 门票 / 机动）
  └─► TripPlan（结构化结果）
        │  SSE result 事件
        ▼
Vue 前端（实时进度 + 行程 / 预算 / 路线图渲染）
```

## 🛠 技术栈

- **后端**：Python 3.11 · FastAPI · Pydantic v2 · OpenAI SDK（DeepSeek，OpenAI 兼容）
- **前端**：Vue 3 · TypeScript · Vite
- **检索**：自研特征哈希向量化 + 余弦相似度（接口兼容 Chroma / Milvus，可平滑升级）
- **LLM**：DeepSeek `deepseek-chat`，JSON Mode + Function Calling
- **MCP**：官方 MCP SDK（`mcp==1.28.1`），把多 Agent 能力暴露成 MCP 工具（stdio + streamable-http）
- **部署**：Docker + docker-compose，前端 nginx 托管 + 反向代理
- **测试/CI**：pytest 冒烟测试（41 个，无 key 全绿）+ GitHub Actions（push 到 main 自动跑后端测试与前端构建）
- **存储/缓存**：Redis（可选）——`app/store.py` KV 抽象双后端，连不上自动回退进程内内存
- **可观测性**：`app/metrics.py` 轻量度量（阶段耗时 p50/p95、降级/工具/缓存计数）+ `GET /api/metrics`
- **评估**：`eval/` 套件——golden cases 不变式校验 + cold/warm 缓存收益（规则引擎 / `--with-llm` 双轨）
- **云端**：Render 蓝图（`render.yaml`）前后端一键部署，免费拿简历 URL

## 🚀 本地运行

```bash
# 1. 配置 API key
cd backend
cp .env.example .env      # 填入 DEEPSEEK_API_KEY

# 2. 后端
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 3. 前端（另开终端）
cd frontend
npm install
node node_modules/vite/bin/vite.js --host 127.0.0.1   # 或 npm run dev
```

打开 `http://127.0.0.1:5173`。健康检查：`GET /api/health`。

## 🐳 Docker 运行（全栈一键启动）

前置条件：先创建 `backend/.env`（`cp backend/.env.example backend/.env`，填入 `DEEPSEEK_API_KEY`）——compose 靠它注入 API key，镜像本身不含密钥。

```bash
docker compose up --build     # 构建并启动
docker compose up -d          # 后台运行
docker compose logs -f        # 查看日志
docker compose down           # 停止
```

启动后：
- 前端：`http://localhost:5173`
- 后端健康检查：`http://localhost:8000/api/health`
- 可观测性：`http://localhost:8000/api/metrics`
- MCP 端点：`http://localhost:8000/mcp`

> compose 会先启动 `redis` 服务并等它健康检查通过，再用 `environment: REDIS_URL=redis://redis:6379`
> 显式覆盖 `.env`（旧 `.env` 可能没有该变量）。**Redis 挂了后端也能靠内存回退兜底运行**，
> `/api/metrics` 里的 `cache.backend` 能直接看到当前用的是哪种后端。

## ☁️ 云端部署（Render 免费，简历挂 URL）

仓库推到 GitHub 后，用仓库根目录的 `render.yaml` 蓝图一键部署前后端：

1. **推 GitHub**：见下方「推到 GitHub」。
2. **连 Render**：打开 https://dashboard.render.com → **New → Blueprint** → 选择本仓库。
3. 等几分钟两个服务自动构建上线。
4. 填 key：`trip-planner-backend` → **Environment** → 添加 `DEEPSEEK_API_KEY`（render.yaml 里 `sync:false`，key 只存 Render 后台，镜像里永远没有）。

部署后：
- 前端（简历 URL）：`https://trip-planner-frontend.onrender.com`
- 后端健康检查：`https://trip-planner-backend.onrender.com/api/health`
- MCP 端点：`https://trip-planner-backend.onrender.com/mcp`

> ⚠️ 免费档：空闲 15 分钟休眠，首次访问冷启动 ~50s；`onrender.com` 国内访问可能需代理，给国内面试官演示建议录屏备用。

## ✅ 测试与 CI

```bash
cd backend
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -v      # 41 个测试，秒级完成、无 key 全绿
```

- 覆盖：健康检查、`travel_minutes` 数学正确性、MCP 5 工具注册、多 Agent **降级路径**（强制 LLM 失败 → 规则引擎兜底，CI 无 API key 也能全绿）、会话记忆（prepare/remember 合并、8 上限）、RAG/LLM 缓存命中、`/api/metrics` 端点、eval 套件通过率
- CI：`.github/workflows/ci.yml`，push 到 `main` 自动跑后端 pytest + 前端类型检查与构建

## 🧠 工程化增量：会话记忆 · Redis 缓存 · 可观测性 · Agent 评估

教程骨架之外的差异化工程能力，每项都带**可量化指标**（面试直接报数字）。

### 1. 会话记忆（Session Memory）

`session_id`（前端 localStorage 持久化）让多轮规划"记住"用户偏好：兴趣做**去重并集**（上限 8 个）、
风格/预算仅当本次用的是 schema 默认值时回填、目的地与备注累积；下一轮自动沿用历史偏好，
响应回显「已记住你的偏好：…」横幅。实测两连发：

```text
第 1 次请求 → memory_notes: ["已记住你的偏好：美食、文化", "此前规划过：杭州", "这是你的第 1 次规划"]
第 2 次请求 → memory_notes: ["已记住你的偏好：美食、文化", "此前规划过：杭州", "这是你的第 2 次规划"]
```

实现要点：`prepare()` 用**合并后的请求**规划，`remember()` 用**原始请求**回写档案（避免"历史+本次"
复合值反复入档导致指数膨胀）；`session_id` 用 Pydantic `Field(exclude=True)` 从响应里剔除；
前端点「新会话」重生成 ID 即开启全新记忆。

### 2. 缓存 + Redis 优雅降级

`app/store.py` KV 存储抽象，**Redis / 进程内内存双后端、行为等价**：

- RAG 检索结果缓存 **24h**（相同查询跳过向量化 + 打分）；LLM `chat_json` 响应缓存 **7d**。
- **优雅降级**：无 `REDIS_URL` → 纯内存零网络（本地/CI/Render）；有 `REDIS_URL` 但连不上
  → 1s 探测失败自动回退内存并记录原因。所有 Redis 操作 `try/except`，**Redis 中途挂只退化为 miss + 计数，API 永不挂**。
- 缓存 key 按功能前缀隔离（`rag:` / `llm:json:` / `session:`），命中率分功能统计。
- `chat_with_tools` **刻意不缓存**——保住 ReAct/tool 真实执行的故事，`tool_success_rate` 诚实。

### 3. 可观测性（GET /api/metrics）

`app/metrics.py` 线程安全单例 + 新端点，CI / 评估 / 运维共用一份数据（实测，真实 DeepSeek 跑 2 次规划）：

```json
{
  "requests_total": 2, "llm_calls": 5, "tool_calls": 21, "tool_errors": 0, "rag_errors": 0,
  "fallbacks": {"research": 0, "itinerary": 0},
  "stages": {
    "itinerary": {"count": 2, "mean": 5.97, "p50": 5.21, "p95": 6.74},
    "research":  {"count": 2, "mean": 1.91, "p50": 0.0002, "p95": 3.81},
    "llm":       {"count": 5, "mean": 3.15, "p50": 2.65, "p95": 4.21}
  },
  "cache": {"backend": "memory", "hits": {...}, "misses": {...}, "rag_hit_rate": 0.0}
}
```

（工具成功率 = 21/21 = **100%**；阶段耗时近秩 p50/p95 反映 LLM 调用真实分布。）

### 4. Agent 评估套件（backend/eval/）

15 个 golden case（4 城 × 天数 1/2/3/4/5 × 风格/预算/兴趣组合 + 未知城市兜底）× 硬性不变式校验：
天数匹配 / 每天 3 个互异非空景点 / **景点名必须在知识库内（防幻觉）** / 预算恒等式 /
`per_person == ceil(total/people)` / transport/meals/packing_list/tips 非空。**双轨运行**：

```bash
cd backend
python -m eval.run_eval               # 规则引擎轨（无 key，CI 安全、秒级）
python -m eval.run_eval --with-llm    # 真实 DeepSeek 轨（需 DEEPSEEK_API_KEY）
python -m eval.run_eval --json        # 机器可读输出
```

**cold → warm 两遍**设计：cold 前清一次缓存（测真实延迟），cold→warm 之间**不清**
（warm 测缓存命中率与收益）。规则引擎轨实测数字：

| 指标 | cold（清缓存首跑） | warm（紧接二跑） |
|---|---|---|
| 通过率 pass_rate | **15/15 = 100%** | 15/15 = 100% |
| 幻觉率 hallucination_rate | **0.0**（0/111 slot） | 0.0 |
| 平均耗时 | 0.5 ms | 0.1 ms（**-80%**） |
| RAG 缓存命中率 | 0%（0/15） | **100%（15/15）** |

**真实 LLM 轨实测**（`--with-llm`，本机 DeepSeek，15 case × cold/warm 两遍，修复后复测）：

| 指标 | cold | warm |
|---|---|---|
| 通过率 pass_rate | 15/15 = **100%** | 15/15 = **100%** |
| 幻觉率 hallucination_rate | 0.0 | 0.0 |
| 中位耗时 p50 | 7.02 s | 6.35 s（**-10%**，LLM 响应缓存命中） |
| LLM 缓存命中率 | 0%（0/14） | **100%（14/14）** |
| RAG 缓存命中率 | 0%（0/15） | **100%（15/15）** |
| 工具成功率 tool_success_rate | 130/130 = **100%** | 131/131 = **100%** |

> 首次实测是 **14/15 = 93.3%**，那一例失败（`sh-foodie-1`）是**评估抓到的真实 bug**：LLM 精排
> 把「外滩」重复输出进候选列表，单日行程出现同名景点（violation：Day 1 三个景点不互异）。
> 已在 `_llm_select` 修复（保序去重 + 去重后不足 3 个时用规则版候选补齐），加 3 个回归测试
> 锁定；**修复后复测 15/15 = 100%**。规则轨永远 100% 是确定性路径的体现；真实 LLM 轨
> 回到 100% 正是「评估 → 抓到缺陷 → 修复 → 回归锁定」闭环的证明。

> 工具计数按**本轮增量**报（cold 130 次 / warm 131 次，与 cache_delta 同语义）；规则引擎轨
> 0 次工具调用 → `tool_success_rate` 为 None，`--with-llm` 轨才报告真实工具成功率。

## 🚀 推到 GitHub

```bash
# 1. GitHub 建仓库（New repository，不要勾选 README/.gitignore）
# 2. 关联并推送（自动触发 CI）
git remote add origin https://github.com/<你的用户名>/trip-planner.git
git branch -M main
git push -u origin main
```

## 🔌 MCP（Model Context Protocol）

项目把核心能力暴露成 **MCP 服务端**，任何 MCP 客户端（Claude Desktop / Claude Code / 其他 Agent）都能直接调用。

### 暴露的 5 个工具

| 工具 | 说明 |
|---|---|
| `plan_trip` | 多 Agent 完整行程规划（RAG → 编排 → 工具调用 → 预算），返回完整 TripPlan |
| `search_places` | RAG 语义检索，返回与兴趣最匹配的景点 |
| `list_city_places` | 查询某城市知识库全部景点（北京/上海/杭州/成都） |
| `travel_minutes` | 按经纬度估算市内交通时间（Haversine） |
| `travel_minutes_between_places` | 按景点名估算两个景点间的交通时间 |

### 两种接入方式

**方式一：stdio（本地进程，Claude Code / Claude Desktop）**

项目根目录已内置 `.mcp.json`，Claude Code 会自动发现名为 `trip-planner` 的本地 MCP 服务。也可以手动添加：

```bash
# Claude Code（需先安装后端依赖）
claude mcp add trip-planner -- .venv/Scripts/python.exe -m app.mcp_server --cwd backend

# 或手动编写 .mcp.json
# {"mcpServers": {"trip-planner": {"command": ".venv/Scripts/python.exe", "args": ["-m","app.mcp_server"], "cwd": "backend"}}}
```

**方式二：streamable-http（远程 / Docker）**

后端已把 MCP 挂载到 `/mcp`。Docker 或本地服务起来后：

```json
{
  "mcpServers": {
    "trip-planner-http": { "type": "http", "url": "http://localhost:8000/mcp" }
  }
}
```

### 用 MCP Inspector 调试

```bash
npx @modelcontextprotocol/inspector
# Streamable HTTP → 填 http://localhost:8000/mcp
# 或 STDIO → 命令 .venv/Scripts/python.exe，参数 -m app.mcp_server，cwd backend
```

> 注意：`plan_trip` 内部调用 DeepSeek，预期耗时 10~60 秒；未配置 API key 时自动降级为规则引擎生成。

## 📁 项目结构

```text
backend/app/
  main.py        # FastAPI 路由 + SSE 流式端点 + MCP /mcp 挂载 + GET /api/metrics
  models.py      # Pydantic 数据契约（请求/响应校验，session_id 用 exclude 剔除）
  agents.py      # 三个 Agent + TravelPlanner 编排器 + 工具定义（阶段耗时埋点）
  llm.py         # DeepSeek 封装：JSON mode、ReAct 工具循环、chat_json 响应缓存
  rag.py         # 语义检索：向量化 + 余弦相似度召回（结果缓存 24h）
  store.py       # KV 抽象：Redis / 内存双后端，优雅降级 + 命中率统计
  metrics.py     # 可观测性：阶段耗时 p50/p95、降级/工具/缓存计数
  memory.py      # 会话记忆：session profile 读写、多轮偏好合并
  tools.py       # travel_minutes 工具（Haversine 距离计算）
  data.py        # 景点知识库（4 城市 × 10 个 POI）
  mcp_server.py  # MCP 服务端：5 个工具（plan_trip / search_places / ...）
  eval/          # 评估套件：golden_cases + evaluator + run_eval CLI（cold/warm）
  tests/         # pytest（41 个：健康检查 / 工具 / MCP / 降级 / 记忆 / 缓存 / 度量 / 评估）
  requirements-dev.txt  # 测试依赖（pytest + httpx）
  Dockerfile     # 后端镜像
frontend/
  src/App.vue    # 表单 + SSE 流式进度 + 行程/预算/路线渲染
  Dockerfile     # 前端镜像（node 构建 → nginx 托管）
  nginx.conf.template  # nginx 模板（$PORT/$BACKEND_URL 注入）+ /api、/mcp 反代（SSE 关缓冲）
docker-compose.yml       # 全栈编排（redis + backend + frontend）
render.yaml              # Render 蓝图（云端一键部署）
.github/workflows/ci.yml # CI：后端 pytest + 前端构建
.mcp.json                # Claude Code 本地 MCP 配置（stdio）
```

## 🧠 设计决策（面试高频）

1. **为什么预算 Agent 不用 LLM？** 纯计算交给确定性代码——LLM 不擅长精确算术、按 token 收费、输出不可复现；LLM 只承担「研究、规划」这类推理型任务。
2. **为什么用 SSE 阶段流而不是 token 级流式？** 多 Agent 输出的是结构化 JSON，逐 token 流对用户没有增量价值；阶段事件流清晰展示每一步进展，实现也更可靠。
3. **为什么 RAG 召回和 LLM 精排分开？** 召回阶段宁可多召回保证 recall，精排阶段 LLM 去噪保证 precision——信息检索的标准两阶段架构。
4. **如何防幻觉？** ① 只允许 LLM 从候选列表选择；② 返回名字与真实数据核对；③ 校验失败整层降级。
5. **为什么用 DeepSeek？** OpenAI 兼容协议，成本极低，国内可用；换模型只改 `llm.py` 一处。

## 🗺 后续规划

- 接入地图/POI 实时数据（高德 API），替换本地知识库
- 换神经 embedding API（OpenAI / 智谱）+ Milvus，升级语义检索
- token 级流式输出 LLM 生成的行程解说文案
- 行程持久化 + PDF / 日历导出
