from __future__ import annotations

import json
import time
from math import ceil

from .data import CITY_PLACES, DEFAULT_PLACES
from .llm import chat_json, chat_with_tools, extract_json
from .memory import memory
from .metrics import metrics
from .models import BudgetBreakdown, DayPlan, Place, TripPlan, TripRequest
from .rag import retrieve
from .tools import travel_minutes


# OpenAI 兼容的 function 定义：暴露给 LLM 的工具清单
TRAVEL_MINUTES_TOOL = {
    "type": "function",
    "function": {
        "name": "travel_minutes",
        "description": "估算两个景点之间的市内交通时间（分钟），用于判断行程如何就近安排",
        "parameters": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "起点景点名"},
                "to": {"type": "string", "description": "终点景点名"},
            },
            "required": ["from", "to"],
        },
    },
}


def _exec_tool(name: str, args: dict, by_name: dict[str, Place]) -> dict:
    """工具的真实执行逻辑：LLM 只负责决定"调谁 + 传什么参数"，这里做精确计算。"""
    if name == "travel_minutes":
        a = by_name.get(args.get("from", ""))
        b = by_name.get(args.get("to", ""))
        if not a or not b:
            metrics.inc("tool_calls")
            metrics.inc("tool_errors")
            return {"error": f"未知景点：{args}"}
        metrics.inc("tool_calls")
        return {
            "from": a.name,
            "to": b.name,
            "minutes": travel_minutes(a.lat, a.lng, b.lat, b.lng),
        }
    metrics.inc("tool_calls")
    metrics.inc("tool_errors")
    return {"error": f"未知工具：{name}"}


class DestinationResearchAgent:
    """Pick destination knowledge that matches interests and travel style.

    三层流水线，每层都有降级：
    1) RAG 语义检索：把用户需求向量化，召回最相关的景点（Chroma）
    2) LLM 排序：把候选发给 DeepSeek，按兴趣挑选排序（JSON mode）
    3) 规则打分：无 key / 调用失败时退回的兜底
    """

    def run(self, request: TripRequest) -> list[Place]:
        start = time.perf_counter()
        try:
            # 1) RAG 语义检索，先召回与用户需求最相关的景点
            candidates = self._retrieve_candidates(request)
            if not request.interests:
                return candidates

            # 2) LLM 在候选中挑选排序
            try:
                return self._llm_select(request, candidates)
            except Exception as exc:  # noqa: BLE001
                metrics.record_fallback("research")
                print(f"[DestinationResearchAgent] LLM 不可用，退回规则版：{exc}")
                return self._rule_based(request, candidates)
        finally:
            metrics.observe("research", time.perf_counter() - start)

    def _retrieve_candidates(self, request: TripRequest) -> list[Place]:
        """RAG 召回：把用户需求拼成自然语言查询，向量检索 top-k 景点。

        检索失败时退回本地全量列表，保证系统可用。
        """
        try:
            query = f"{request.destination}旅行 兴趣：{'、'.join(request.interests)} 备注：{request.notes}"
            names = retrieve(query, city=request.destination, top_k=6)
            by_name = {p.name: p for p in (CITY_PLACES.get(request.destination) or DEFAULT_PLACES)}
            picked = [by_name[n] for n in names if n in by_name]
            if picked:
                print(f"[DestinationResearchAgent] RAG 召回：{[p.name for p in picked]}")
                return picked
        except Exception as exc:  # noqa: BLE001
            metrics.inc("rag_errors")
            print(f"[DestinationResearchAgent] RAG 不可用：{exc}")
        return CITY_PLACES.get(request.destination, DEFAULT_PLACES)

    def _rule_based(self, request: TripRequest, places: list[Place]) -> list[Place]:
        interest_words = set(request.interests)
        scored: list[tuple[int, Place]] = []
        for place in places:
            score = 0
            if place.category in interest_words:
                score += 3
            if any(word in place.description for word in interest_words):
                score += 1
            scored.append((score, place))

        return [place for _, place in sorted(scored, key=lambda item: item[0], reverse=True)]

    def _llm_select(self, request: TripRequest, places: list[Place]) -> list[Place]:
        """让 LLM 从候选里挑景点；返回名字再和真实数据核对，防止幻觉。"""
        place_lines = "\n".join(
            f"- {p.name} | 分类:{p.category} | 简介:{p.description}"
            for p in places
        )
        system = (
            "你是资深旅行规划师。根据用户的兴趣和旅行风格，从候选景点中挑选最匹配的并排序。"
            "只能从候选列表里选，严禁编造新景点。"
            '只输出 JSON，格式为 {"places":[{"name":"景点名"},...]}，最多 6 个。'
        )
        user = (
            f"目的地:{request.destination}\n"
            f"兴趣:{','.join(request.interests)}\n"
            f"旅行风格:{request.travel_style}\n"
            f"候选景点:\n{place_lines}\n"
        )
        content = chat_json(system, user)
        data = json.loads(content)
        by_name = {p.name: p for p in places}
        # 保序去重：LLM 可能重复输出同一景点（评估抓到的真实 case：sh-foodie-1）。
        # 候选列表带重会让单日行程出现同名景点，破坏「每天 3 个互异」不变式。
        picked: list[Place] = []
        seen: set[str] = set()
        for item in data.get("places", []):
            name = item.get("name")
            if name in by_name and name not in seen:
                seen.add(name)
                picked.append(by_name[name])
        # 兜底：去重后不足 3 个时，用规则版排序的候选补齐——保证任意一天都能排满 3 个互异景点。
        if len(picked) < 3:
            for place in self._rule_based(request, places):
                if len(picked) >= 3:
                    break
                if place.name not in seen:
                    seen.add(place.name)
                    picked.append(place)
        print(f"[DestinationResearchAgent] LLM 挑选：{[p.name for p in picked]}")
        return picked or self._rule_based(request, places)


class ItineraryAgent:
    """把景点排进每天。LLM + 工具版本：调用 travel_minutes 就近安排、避免重复；
    无 key 或失败时退回规则版。"""

    def run(self, request: TripRequest, places: list[Place]) -> list[DayPlan]:
        start = time.perf_counter()
        try:
            try:
                return self._llm_itinerary(request, places)
            except Exception as exc:  # noqa: BLE001
                metrics.record_fallback("itinerary")
                print(f"[ItineraryAgent] LLM 不可用，退回规则版：{exc}")
                return self._rule_based(request, places)
        finally:
            metrics.observe("itinerary", time.perf_counter() - start)

    def _rule_based(self, request: TripRequest, places: list[Place]) -> list[DayPlan]:
        days: list[DayPlan] = []
        for index in range(request.days):
            morning = places[(index * 2) % len(places)]
            afternoon = places[(index * 2 + 1) % len(places)]
            evening = places[(index * 2 + 2) % len(places)]
            days.append(self._make_day(request, index, morning, afternoon, evening))
        return days

    def _llm_itinerary(self, request: TripRequest, places: list[Place]) -> list[DayPlan]:
        by_name = {p.name: p for p in places}
        place_list = "\n".join(f"- {p.name}（{p.category}）" for p in places)
        system = (
            "你是行程规划师。把可选景点安排进每天的上午/下午/晚上。\n"
            "硬性规则：\n"
            f"1. 共 {request.days} 天，每天恰好 3 个位置（上午/下午/晚上）；\n"
            "2. 同一天内三个景点必须互不相同；\n"
            "3. 尽量让每个可选景点至少出现一次，充分覆盖；只有位置不够时才允许复用，且相邻两天尽量不同；\n"
            "4. 只能用提供的景点名，严禁编造；\n"
            '5. 只输出 JSON，格式：{"days":[{"morning":"景点A","afternoon":"景点B","evening":"景点C"}, ...]}；\n'
            "可以调用 travel_minutes 工具估算两个景点间的交通时间，以便就近安排。"
        )
        user = (
            f"目的地:{request.destination}，旅行风格:{request.travel_style}。\n"
            f"可选景点:\n{place_list}\n"
        )
        content = chat_with_tools(
            system,
            user,
            [TRAVEL_MINUTES_TOOL],
            lambda name, args: _exec_tool(name, args, by_name),
        )
        data = extract_json(content)
        slots = data["days"][: request.days]
        if len(slots) != request.days:
            raise ValueError(f"LLM 只返回了 {len(slots)} 天，需要 {request.days} 天")

        days: list[DayPlan] = []
        for index, slot in enumerate(slots):
            names = [slot[key] for key in ("morning", "afternoon", "evening")]
            if len(set(names)) != 3:
                raise ValueError(f"第 {index + 1} 天存在重复景点：{names}")
            chosen = [by_name.get(name) for name in names]
            if any(p is None for p in chosen):
                raise ValueError(f"第 {index + 1} 天包含未知景点：{names}")
            days.append(self._make_day(request, index, *chosen))
        print(f"[ItineraryAgent] LLM 生成 {len(days)} 天行程")
        return days

    @staticmethod
    def _make_day(
        request: TripRequest,
        index: int,
        morning: Place,
        afternoon: Place,
        evening: Place,
    ) -> DayPlan:
        ticket_cost = (morning.ticket + afternoon.ticket + evening.ticket) * request.people
        meal_cost = ItineraryAgent._meal_cost(request.budget_level) * request.people
        transport_cost = ItineraryAgent._transport_cost(request.budget_level, request.people)
        return DayPlan(
            day=index + 1,
            theme=f"{request.destination}第 {index + 1} 天：{morning.category} + {afternoon.category}",
            morning=morning,
            afternoon=afternoon,
            evening=evening,
            transport=ItineraryAgent._transport_text(request.budget_level),
            meals=ItineraryAgent._meals(request.destination, request.travel_style),
            estimated_cost=ticket_cost + meal_cost + transport_cost,
            teacher_note=ItineraryAgent._style_note(request.travel_style),
        )

    @staticmethod
    def _style_note(style: str) -> str:
        return {
            "relaxed": "今天按慢节奏安排，留出咖啡和临时调整时间。",
            "classic": "今天覆盖经典景点，适合第一次到访。",
            "deep": "今天强调文化背景和深度体验，少赶路多理解。",
            "family": "今天减少高强度移动，适合亲子或多人同行。",
            "foodie": "今天把美食街区和本地餐饮体验放到更重要位置。",
        }[style]

    @staticmethod
    def _meal_cost(level: str) -> int:
        return {"economy": 90, "standard": 160, "comfort": 260}[level]

    @staticmethod
    def _transport_cost(level: str, people: int) -> int:
        per_day = {"economy": 45, "standard": 80, "comfort": 160}[level]
        return per_day * people

    @staticmethod
    def _transport_text(level: str) -> str:
        return {
            "economy": "地铁/公交为主，必要时短途打车。",
            "standard": "地铁 + 网约车组合，控制换乘次数。",
            "comfort": "网约车为主，优先降低体力消耗。",
        }[level]

    @staticmethod
    def _meals(destination: str, style: str) -> list[str]:
        local_food = {
            "北京": ["炸酱面", "铜锅涮肉", "豆汁可选但不强推"],
            "上海": ["本帮菜", "生煎", "咖啡街区简餐"],
            "杭州": ["西湖醋鱼", "片儿川", "龙井茶点"],
            "成都": ["担担面", "火锅", "盖碗茶"],
        }.get(destination, ["本地早餐", "特色正餐", "轻食或夜宵"])
        return local_food if style == "foodie" else local_food[:2] + ["就近简餐"]


class BudgetAgent:
    def run(self, request: TripRequest, day_plans: list[DayPlan]) -> BudgetBreakdown:
        start = time.perf_counter()
        try:
            return self._compute(request, day_plans)
        finally:
            metrics.observe("budget", time.perf_counter() - start)

    @staticmethod
    def _compute(request: TripRequest, day_plans: list[DayPlan]) -> BudgetBreakdown:
        lodging_per_room = {"economy": 260, "standard": 520, "comfort": 900}[request.budget_level]
        rooms = ceil(request.people / 2)
        lodging = lodging_per_room * rooms * max(request.days - 1, 1)
        food = {"economy": 90, "standard": 160, "comfort": 260}[request.budget_level] * request.people * request.days
        transport = {"economy": 45, "standard": 80, "comfort": 160}[request.budget_level] * request.people * request.days
        tickets = sum(
            day.morning.ticket + day.afternoon.ticket + day.evening.ticket for day in day_plans
        ) * request.people
        misc = ceil((lodging + food + transport + tickets) * 0.12)
        total = lodging + food + transport + tickets + misc
        return BudgetBreakdown(
            lodging=lodging,
            food=food,
            transport=transport,
            tickets=tickets,
            misc=misc,
            total=total,
            per_person=ceil(total / request.people),
        )


class TravelPlanner:
    def __init__(self) -> None:
        self.researcher = DestinationResearchAgent()
        self.itinerary = ItineraryAgent()
        self.budget = BudgetAgent()

    def prepare(self, request: TripRequest) -> TripRequest:
        """把会话记忆里的历史偏好合并进本次请求（无 session_id 则原样返回）。"""
        return memory.prepare(request)

    def remember(self, request: TripRequest) -> list[str]:
        """用原始请求更新会话档案，返回 memory_notes 回显文案。"""
        return memory.remember(request)

    def plan(self, request: TripRequest) -> TripPlan:
        prepared = self.prepare(request)
        places = self.researcher.run(prepared)
        day_plans = self.itinerary.run(prepared, places)
        budget = self.budget.run(prepared, day_plans)
        plan = self._assemble(prepared, places, day_plans, budget)
        # 用原始 request 记录，避免「历史 + 本次」合并值再次入档案导致指数膨胀
        plan.memory_notes = self.remember(request)
        return plan

    def _assemble(
        self,
        request: TripRequest,
        places: list[Place],
        day_plans: list[DayPlan],
        budget: BudgetBreakdown,
    ) -> TripPlan:
        route_points = self._dedupe_places(day_plans)
        summary = (
            f"为 {request.people} 人设计 {request.days} 天{request.destination}行程，"
            f"风格为 {request.travel_style}，预算档位为 {request.budget_level}。"
        )
        return TripPlan(
            title=f"{request.destination} {request.days} 天游玩计划",
            destination=request.destination,
            summary=summary,
            request=request,
            days=day_plans,
            budget=budget,
            route_points=route_points,
            packing_list=self._packing_list(request),
            tips=self._tips(request),
        )

    @staticmethod
    def _dedupe_places(days: list[DayPlan]) -> list[Place]:
        seen: set[str] = set()
        result: list[Place] = []
        for day in days:
            for place in (day.morning, day.afternoon, day.evening):
                if place.name not in seen:
                    seen.add(place.name)
                    result.append(place)
        return result

    @staticmethod
    def _packing_list(request: TripRequest) -> list[str]:
        base = ["身份证件", "充电器/充电宝", "舒适步行鞋", "常用药", "雨伞或轻便雨衣"]
        if request.travel_style in {"deep", "classic"}:
            base.append("提前预约博物馆/热门景点")
        if request.travel_style == "family":
            base.append("儿童零食与备用衣物")
        return base

    @staticmethod
    def _tips(request: TripRequest) -> list[str]:
        tips = [
            "热门景点建议提前预约，并预留安检和排队时间。",
            "每天最多安排 2-3 个重点点位，避免行程过载。",
            "预算为估算值，真实价格会受节假日和酒店位置影响。",
        ]
        if request.notes:
            tips.append(f"已考虑你的补充要求：{request.notes}")
        return tips
