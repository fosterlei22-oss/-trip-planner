from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import TripRequest
from .store import SESSION_PREFIX, get_store

# 会话记忆保留时长（秒）：90 天
SESSION_TTL = 90 * 24 * 3600

# TripRequest.interests 的 schema 上限，合并时必须手工保证不超
MAX_INTERESTS = 8


@dataclass
class MemoryProfile:
    """会话记忆档案：从多轮请求里累积的用户偏好。

    只存「跨轮可沿用」的信息；destination/days/people/start_date 是当次输入不存。
    """

    interests: list[str] = field(default_factory=list)
    travel_style: str | None = None
    budget_level: str | None = None
    destinations: list[str] = field(default_factory=list)  # 每次访问的完整历史（可重复）
    notes: list[str] = field(default_factory=list)
    visits: int = 0
    updated_at: str = ""


class MemoryStore:
    """基于 KVStore 的会话记忆：prepare 合并历史偏好进请求，remember 回写档案。

    每次操作都走 get_store() 单例（而非构造时固化），reset_store() 重新探测
    Redis/内存后端后记忆自动跟随。
    """

    def get_profile(self, session_id: str) -> MemoryProfile | None:
        raw = get_store().get(SESSION_PREFIX + session_id)
        if raw is None:
            return None
        return MemoryProfile(**raw)

    # ---- 合并：请求 → 带历史偏好的请求 ----
    def prepare(self, request: TripRequest) -> TripRequest:
        """把历史偏好合并进本次请求（兴趣并集、style/budget 仅在未显式指定时沿用）。

        无 session_id 或尚无档案时原样返回，行为与旧版完全一致。
        """
        if not request.session_id:
            return request
        profile = self.get_profile(request.session_id)
        if profile is None:
            return request

        update: dict = {}

        # 兴趣：本次在前、历史补足，手工保证 ≤8（model_copy 跳过重校验）
        merged = list(request.interests)
        for interest in profile.interests:
            if interest not in merged and len(merged) < MAX_INTERESTS:
                merged.append(interest)
        if merged != request.interests:
            update["interests"] = merged

        # style/budget：仅当请求用的是 schema 默认值（可视为「未指定」）且档案有记录时沿用
        if request.travel_style == "classic" and profile.travel_style:
            update["travel_style"] = profile.travel_style
        if request.budget_level == "standard" and profile.budget_level:
            update["budget_level"] = profile.budget_level

        return request.model_copy(update=update)

    # ---- 回写：请求 → 更新档案 ----
    def remember(self, request: TripRequest) -> list[str]:
        """用**原始请求**更新会话档案，返回给用户看的 memory_notes。

        必须用原始请求而非 prepare 合并后的：否则重复合并会指数膨胀。
        """
        if not request.session_id:
            return []
        key = SESSION_PREFIX + request.session_id
        profile = self.get_profile(request.session_id) or MemoryProfile()

        # 兴趣：档案在前、本次补足（按时间累积，顺序稳定）
        for interest in request.interests:
            if interest not in profile.interests:
                profile.interests.append(interest)
        profile.interests = profile.interests[:MAX_INTERESTS]

        # style/budget：只记录「显式指定」的
        if request.travel_style != "classic":
            profile.travel_style = request.travel_style
        if request.budget_level != "standard":
            profile.budget_level = request.budget_level

        profile.destinations.append(request.destination)
        if request.notes and request.notes not in profile.notes:
            profile.notes.append(request.notes)
        profile.notes = profile.notes[-5:]

        profile.visits += 1
        profile.updated_at = datetime.now().isoformat(timespec="seconds")

        get_store().set(
            key,
            {
                "interests": profile.interests,
                "travel_style": profile.travel_style,
                "budget_level": profile.budget_level,
                "destinations": profile.destinations,
                "notes": profile.notes,
                "visits": profile.visits,
                "updated_at": profile.updated_at,
            },
            ttl=SESSION_TTL,
        )
        return self._build_notes(profile)

    @staticmethod
    def _build_notes(profile: MemoryProfile) -> list[str]:
        """把档案转成给用户看的回显文案。"""
        notes: list[str] = []
        if profile.interests:
            notes.append(f"已记住你的偏好：{'、'.join(profile.interests)}")
        # 目的地去重但保留出现顺序
        seen: list[str] = []
        for dest in profile.destinations:
            if dest not in seen:
                seen.append(dest)
        if seen:
            notes.append(f"此前规划过：{'、'.join(seen)}")
        notes.append(f"这是你的第 {profile.visits} 次规划")
        return notes


# 模块级单例：agents.py / main.py 共用
memory = MemoryStore()
