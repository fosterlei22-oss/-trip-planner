# 🧭 智能旅行助手 · LLM 多 Agent 应用

一个从零实现的 **LLM 多 Agent 应用**：输入目的地、天数、预算、兴趣，系统通过「RAG 语义检索 → 多 Agent 编排 → 工具调用 → SSE 流式输出」实时生成完整旅行计划（每日行程、预算拆分、路线图、打包清单）。

后端 FastAPI + Pydantic，前端 Vue 3 + TypeScript。研究、行程两个 Agent 由 DeepSeek 驱动，预算 Agent 保持确定性计算，形成「**LLM 决策 + 代码执行**」的异构多 Agent 架构。

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

## 📁 项目结构

```text
backend/app/
  main.py        # FastAPI 路由 + SSE 流式端点
  models.py      # Pydantic 数据契约（请求/响应校验）
  agents.py      # 三个 Agent + TravelPlanner 编排器 + 工具定义
  llm.py         # DeepSeek 封装：JSON mode、ReAct 工具循环、JSON 提取
  rag.py         # 语义检索：向量化 + 余弦相似度召回
  tools.py       # travel_minutes 工具（Haversine 距离计算）
  data.py        # 景点知识库（4 城市 × 10 个 POI）
frontend/src/
  App.vue        # 表单 + SSE 流式进度 + 行程/预算/路线渲染
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
