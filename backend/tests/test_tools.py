"""travel_minutes 工具的数学正确性测试（纯函数，无需网络 / API key）。"""
from app.tools import haversine_km, travel_minutes


def test_same_point_is_floor_10_minutes():
    # 同一点距离为 0，按设计下限给 10 分钟
    assert travel_minutes(0.0, 0.0, 0.0, 0.0) == 10


def test_known_distance_haversine():
    # 1 度纬度 ≈ 111.19 km
    km = haversine_km(0.0, 0.0, 0.0, 1.0)
    assert 110 < km < 112


def test_known_distance_travel_minutes():
    # 111.19km / 24km/h * 60 ≈ 278 分钟
    assert travel_minutes(0.0, 0.0, 0.0, 1.0) == 278


def test_between_places_hangzhou_reasonable():
    # 知识库真实坐标：西湖苏堤 → 浙江省博物馆（相距很近），应在合理分钟数内
    from app.mcp_server import travel_minutes_between_places

    minutes = travel_minutes_between_places("杭州", "西湖苏堤", "浙江省博物馆")
    assert 10 <= minutes <= 120


def test_between_places_unknown_raises():
    from app.mcp_server import travel_minutes_between_places

    try:
        travel_minutes_between_places("杭州", "不存在的景点", "西湖苏堤")
        raise AssertionError("应当抛出 ValueError")
    except ValueError:
        pass
