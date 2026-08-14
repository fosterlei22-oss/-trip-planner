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
- **测试/CI**：pytest 冒烟测试 + GitHub Actions（push 到 main 自动跑后端测试与前端构建）
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
- MCP 端点：`http://localhost:8000/mcp`

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
.venv/Scripts/python -m pytest -v      # 11 个冒烟测试，秒级完成
```

- 覆盖：健康检查、`travel_minutes` 数学正确性、MCP 5 工具注册、多 Agent **降级路径**（强制 LLM 失败 → 规则引擎兜底，CI 无 API key 也能全绿）
- CI：`.github/workflows/ci.yml`，push 到 `main` 自动跑后端 pytest + 前端类型检查与构建

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
  main.py        # FastAPI 路由 + SSE 流式端点 + MCP /mcp 挂载
  models.py      # Pydantic 数据契约（请求/响应校验）
  agents.py      # 三个 Agent + TravelPlanner 编排器 + 工具定义
  llm.py         # DeepSeek 封装：JSON mode、ReAct 工具循环、JSON 提取
  rag.py         # 语义检索：向量化 + 余弦相似度召回
  tools.py       # travel_minutes 工具（Haversine 距离计算）
  data.py        # 景点知识库（4 城市 × 10 个 POI）
  mcp_server.py  # MCP 服务端：5 个工具（plan_trip / search_places / ...）
  tests/         # pytest 冒烟测试（健康检查 / 工具 / MCP / 降级路径）
  requirements-dev.txt  # 测试依赖（pytest + httpx）
  Dockerfile     # 后端镜像
frontend/
  src/App.vue    # 表单 + SSE 流式进度 + 行程/预算/路线渲染
  Dockerfile     # 前端镜像（node 构建 → nginx 托管）
  nginx.conf.template  # nginx 模板（$PORT/$BACKEND_URL 注入）+ /api、/mcp 反代（SSE 关缓冲）
docker-compose.yml       # 全栈编排（backend + frontend）
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
