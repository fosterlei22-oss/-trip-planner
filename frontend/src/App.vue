<script setup lang="ts">
import { computed, ref } from "vue";
import type { BudgetLevel, Place, TravelStyle, TripPlan, TripRequest } from "./types";

const API_URL = "/api/trip/plan/stream";

const interestOptions = ["历史", "文化", "自然", "美食", "摄影", "休闲", "城市"];
const styleLabels: Record<TravelStyle, string> = {
  relaxed: "慢节奏",
  classic: "经典路线",
  deep: "深度体验",
  family: "亲子友好",
  foodie: "美食优先"
};
const budgetLabels: Record<BudgetLevel, string> = {
  economy: "经济",
  standard: "标准",
  comfort: "舒适"
};

const form = ref<TripRequest>({
  destination: "杭州",
  days: 3,
  people: 2,
  budget_level: "standard",
  travel_style: "classic",
  interests: ["文化", "美食", "休闲"],
  start_date: null,
  notes: ""
});

const plan = ref<TripPlan | null>(null);
const loading = ref(false);
const error = ref("");
const progress = ref("");

// ---- 会话记忆：localStorage 持久化 session_id，多轮规划沿用历史偏好 ----
const SESSION_KEY = "trip_planner_session_id";

function fallbackUuid(): string {
  const s = () => Math.random().toString(16).slice(2, 8);
  return `${s()}-${s()}-${s()}`;
}

function generateUuid(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : fallbackUuid();
}

function getOrCreateSessionId(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const fresh = generateUuid();
    localStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    return generateUuid(); // 隐私模式 / localStorage 不可用时退化为内存会话
  }
}

const sessionId = ref<string>(getOrCreateSessionId());

function newSession() {
  // 换新 ID = 后端视为全新会话（记忆从零开始）
  sessionId.value = generateUuid();
  try {
    localStorage.setItem(SESSION_KEY, sessionId.value);
  } catch {
    /* 忽略存储失败 */
  }
  plan.value = null;
  error.value = "";
  progress.value = "";
}

const budgetRows = computed(() => {
  if (!plan.value) return [];
  return [
    ["住宿", plan.value.budget.lodging],
    ["餐饮", plan.value.budget.food],
    ["交通", plan.value.budget.transport],
    ["门票", plan.value.budget.tickets],
    ["机动", plan.value.budget.misc]
  ];
});

const routePoints = computed(() => plan.value?.route_points ?? []);

const mapViewBox = computed(() => {
  const points = routePoints.value;
  if (points.length === 0) return "0 0 600 300";
  return "0 0 600 300";
});

function toggleInterest(item: string) {
  const current = form.value.interests;
  form.value.interests = current.includes(item)
    ? current.filter((interest) => interest !== item)
    : [...current, item];
}

async function generatePlan() {
  loading.value = true;
  error.value = "";
  progress.value = "正在连接...";
  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form.value, session_id: sessionId.value })
    });
    if (!response.ok || !response.body) {
      throw new Error(`生成失败：HTTP ${response.status}`);
    }

    // 逐段读取 SSE 流
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE 事件以空行分隔，按 \n\n 切分逐个处理
      let splitIndex;
      while ((splitIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, splitIndex);
        buffer = buffer.slice(splitIndex + 2);

        let eventName = "message";
        let data = "";
        for (const line of rawEvent.split("\n")) {
          if (line.startsWith("event:")) eventName = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;

        const payload = JSON.parse(data);
        if (eventName === "stage") {
          progress.value = payload.message;
        } else if (eventName === "result") {
          plan.value = payload as TripPlan;
        }
      }
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "生成失败，请检查后端服务是否已启动。";
  } finally {
    loading.value = false;
  }
}

function exportJson() {
  if (!plan.value) return;
  const blob = new Blob([JSON.stringify(plan.value, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${plan.value.destination}-trip-plan.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function pointPosition(place: Place, index: number, total: number) {
  const safeTotal = Math.max(total - 1, 1);
  const x = 64 + (index / safeTotal) * 472;
  const y = 92 + Math.sin(index * 1.35) * 52 + (index % 2) * 42;
  return { x, y, label: place.name.slice(0, 6) };
}

generatePlan();
</script>

<template>
  <main class="app-shell">
    <aside class="planner-panel">
      <div class="panel-heading">
        <p class="eyebrow">Chapter 13 Project</p>
        <h1>智能旅行助手</h1>
      </div>

      <form class="trip-form" @submit.prevent="generatePlan">
        <label>
          <span>目的地</span>
          <input v-model="form.destination" placeholder="例如：杭州" />
        </label>

        <div class="form-grid">
          <label>
            <span>天数</span>
            <input v-model.number="form.days" type="number" min="1" max="14" />
          </label>
          <label>
            <span>人数</span>
            <input v-model.number="form.people" type="number" min="1" max="12" />
          </label>
        </div>

        <label>
          <span>出发日期</span>
          <input v-model="form.start_date" type="date" />
        </label>

        <section class="choice-group">
          <span>预算档位</span>
          <div class="segmented">
            <button
              v-for="(label, key) in budgetLabels"
              :key="key"
              type="button"
              :class="{ active: form.budget_level === key }"
              @click="form.budget_level = key as BudgetLevel"
            >
              {{ label }}
            </button>
          </div>
        </section>

        <section class="choice-group">
          <span>旅行风格</span>
          <div class="segmented wrap">
            <button
              v-for="(label, key) in styleLabels"
              :key="key"
              type="button"
              :class="{ active: form.travel_style === key }"
              @click="form.travel_style = key as TravelStyle"
            >
              {{ label }}
            </button>
          </div>
        </section>

        <section class="choice-group">
          <span>兴趣偏好</span>
          <div class="chips">
            <button
              v-for="item in interestOptions"
              :key="item"
              type="button"
              :class="{ active: form.interests.includes(item) }"
              @click="toggleInterest(item)"
            >
              {{ item }}
            </button>
          </div>
        </section>

        <label>
          <span>补充要求</span>
          <textarea v-model="form.notes" rows="4" placeholder="例如：不想太赶，晚上想安排小吃街" />
        </label>

        <button class="primary-button" :disabled="loading" type="submit">
          {{ loading ? "生成中..." : "生成行程" }}
        </button>

        <p v-if="progress" style="color:#2f7d70;margin-top:10px;font-size:14px;">{{ progress }}</p>
        <p v-if="error" class="error-text">{{ error }}</p>
      </form>
    </aside>

    <section class="result-panel" v-if="plan">
      <header class="result-header">
        <div>
          <p class="eyebrow">Generated Plan</p>
          <h2>{{ plan.title }}</h2>
          <p>{{ plan.summary }}</p>
        </div>
        <div class="header-actions">
          <button class="secondary-button" type="button" @click="newSession">新会话</button>
          <button class="secondary-button" type="button" @click="exportJson">导出 JSON</button>
        </div>
      </header>

      <div v-if="plan.memory_notes?.length" class="memory-banner">
        <p v-for="note in plan.memory_notes" :key="note">🧠 {{ note }}</p>
      </div>

      <section class="overview-grid">
        <article class="metric">
          <span>总预算</span>
          <strong>¥{{ plan.budget.total }}</strong>
        </article>
        <article class="metric">
          <span>人均</span>
          <strong>¥{{ plan.budget.per_person }}</strong>
        </article>
        <article class="metric">
          <span>点位</span>
          <strong>{{ routePoints.length }}</strong>
        </article>
      </section>

      <section class="map-section">
        <div class="section-title">
          <h3>路线概览</h3>
          <span>{{ plan.destination }}</span>
        </div>
        <svg :viewBox="mapViewBox" role="img" aria-label="旅行路线示意图">
          <polyline
            :points="routePoints.map((p, i) => {
              const pos = pointPosition(p, i, routePoints.length);
              return `${pos.x},${pos.y}`;
            }).join(' ')"
            fill="none"
            stroke="#2f7d70"
            stroke-width="4"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <g v-for="(place, index) in routePoints" :key="place.name">
            <circle
              :cx="pointPosition(place, index, routePoints.length).x"
              :cy="pointPosition(place, index, routePoints.length).y"
              r="13"
              fill="#f4b942"
              stroke="#2b2e34"
              stroke-width="3"
            />
            <text
              :x="pointPosition(place, index, routePoints.length).x"
              :y="pointPosition(place, index, routePoints.length).y + 34"
              text-anchor="middle"
            >
              {{ pointPosition(place, index, routePoints.length).label }}
            </text>
          </g>
        </svg>
      </section>

      <section class="content-grid">
        <div class="itinerary-list">
          <div class="section-title">
            <h3>每日行程</h3>
            <span>可编辑备注</span>
          </div>
          <article v-for="day in plan.days" :key="day.day" class="day-card">
            <div class="day-card-header">
              <strong>Day {{ day.day }}</strong>
              <input v-model="day.theme" />
            </div>
            <div class="timeline">
              <p><b>上午</b>{{ day.morning.name }}：{{ day.morning.description }}</p>
              <p><b>下午</b>{{ day.afternoon.name }}：{{ day.afternoon.description }}</p>
              <p><b>晚上</b>{{ day.evening.name }}：{{ day.evening.description }}</p>
            </div>
            <div class="day-meta">
              <span>{{ day.transport }}</span>
              <span>¥{{ day.estimated_cost }}</span>
            </div>
            <textarea v-model="day.teacher_note" rows="2" />
          </article>
        </div>

        <aside class="side-stack">
          <section class="info-block">
            <div class="section-title">
              <h3>预算拆分</h3>
              <span>估算</span>
            </div>
            <div class="budget-row" v-for="[name, amount] in budgetRows" :key="name">
              <span>{{ name }}</span>
              <strong>¥{{ amount }}</strong>
            </div>
          </section>

          <section class="info-block">
            <div class="section-title">
              <h3>打包清单</h3>
              <span>{{ plan.packing_list.length }} 项</span>
            </div>
            <ul>
              <li v-for="item in plan.packing_list" :key="item">{{ item }}</li>
            </ul>
          </section>

          <section class="info-block">
            <div class="section-title">
              <h3>旅行提醒</h3>
              <span>Tips</span>
            </div>
            <ul>
              <li v-for="tip in plan.tips" :key="tip">{{ tip }}</li>
            </ul>
          </section>
        </aside>
      </section>
    </section>
  </main>
</template>
