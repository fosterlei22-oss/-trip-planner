"""Golden 用例：4 座城市 × 天数/风格/预算/兴趣的组合 + 未知城市兜底验证。

每个用例的键与 TripRequest 字段一致（多一个 `id` 仅供报告定位），
可直接解包成 payload 构造 TripRequest。覆盖：

- 天数 1/2/3/4/5；风格 classic/relaxed/family/foodie/deep；
  预算 economy/standard/comfort；
- 空兴趣（RAG 召回后直接返回）、多兴趣（LLM/规则排序压力）；
- 含 notes（补充分求，影响 tips）；
- 未知城市「重庆」：CITY_PLACES 查不到 → DEFAULT_PLACES 兜底，
  验证系统不崩溃、且不产生知识库外景点（幻觉）。
"""

CASES: list[dict] = [
    # ---------- 北京 ----------
    {
        "id": "bj-classic-3",
        "destination": "北京",
        "days": 3,
        "people": 2,
        "budget_level": "standard",
        "travel_style": "classic",
        "interests": ["历史", "文化"],
    },
    {
        "id": "bj-family-2",
        "destination": "北京",
        "days": 2,
        "people": 4,
        "budget_level": "comfort",
        "travel_style": "family",
        "interests": ["文化", "休闲"],
        "notes": "带老人孩子，别安排太赶",
    },
    {
        "id": "bj-economy-1",
        "destination": "北京",
        "days": 1,
        "people": 2,
        "budget_level": "economy",
        "travel_style": "classic",
        "interests": ["历史"],
    },
    {
        "id": "bj-multi-interest",
        "destination": "北京",
        "days": 3,
        "people": 2,
        "budget_level": "standard",
        "travel_style": "deep",
        "interests": ["历史", "文化", "美食", "摄影"],
    },
    # ---------- 上海 ----------
    {
        "id": "sh-foodie-1",
        "destination": "上海",
        "days": 1,
        "people": 2,
        "budget_level": "standard",
        "travel_style": "foodie",
        "interests": ["美食"],
    },
    {
        "id": "sh-deep-5",
        "destination": "上海",
        "days": 5,
        "people": 2,
        "budget_level": "economy",
        "travel_style": "deep",
        "interests": ["城市", "摄影"],
    },
    {
        "id": "sh-comfort-2",
        "destination": "上海",
        "days": 2,
        "people": 2,
        "budget_level": "comfort",
        "travel_style": "classic",
        "interests": ["城市", "美食"],
    },
    {
        "id": "sh-relaxed-3",
        "destination": "上海",
        "days": 3,
        "people": 3,
        "budget_level": "standard",
        "travel_style": "relaxed",
        "interests": ["休闲", "城市"],
        "notes": "想看外滩夜景",
    },
    # ---------- 杭州 ----------
    {
        "id": "hz-relaxed-3",
        "destination": "杭州",
        "days": 3,
        "people": 2,
        "budget_level": "standard",
        "travel_style": "relaxed",
        "interests": ["自然"],
    },
    {
        "id": "hz-empty-interests",
        "destination": "杭州",
        "days": 2,
        "people": 3,
        "budget_level": "comfort",
        "travel_style": "classic",
        "interests": [],
    },
    {
        "id": "hz-foodie-1",
        "destination": "杭州",
        "days": 1,
        "people": 2,
        "budget_level": "standard",
        "travel_style": "foodie",
        "interests": ["美食"],
    },
    # ---------- 成都 ----------
    {
        "id": "cd-foodie-3",
        "destination": "成都",
        "days": 3,
        "people": 2,
        "budget_level": "standard",
        "travel_style": "foodie",
        "interests": ["美食", "休闲"],
    },
    {
        "id": "cd-economy-4",
        "destination": "成都",
        "days": 4,
        "people": 1,
        "budget_level": "economy",
        "travel_style": "deep",
        "interests": ["文化", "历史"],
    },
    {
        "id": "cd-family-2",
        "destination": "成都",
        "days": 2,
        "people": 4,
        "budget_level": "standard",
        "travel_style": "family",
        "interests": ["美食", "休闲"],
        # 备注要与其他成都用例不同，否则 RAG 查询撞 key，cold 命中率就不干净了
        "notes": "带两个小孩，安排轻松些，晚上逛宽窄巷子",
    },
    # ---------- 未知城市（DEFAULT_PLACES 兜底） ----------
    {
        "id": "unknown-city-chongqing",
        "destination": "重庆",
        "days": 2,
        "people": 2,
        "budget_level": "standard",
        "travel_style": "classic",
        "interests": ["美食"],
    },
]

# 用于「未知城市兜底」专项验证的用例 id（检索返回空 → 走默认景点库）
UNKNOWN_CITY_CASES = ["unknown-city-chongqing"]
