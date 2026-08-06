from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两个经纬度之间的大圆距离（公里）。"""
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def travel_minutes(
    lat1: float, lng1: float, lat2: float, lng2: float, speed_kmh: float = 24.0
) -> int:
    """估算两个景点之间的市内交通时间（分钟）。

    假设市内综合时速约 24km/h（含红绿灯、停车、步行），下限 10 分钟。
    """
    km = haversine_km(lat1, lng1, lat2, lng2)
    return max(10, int(km / speed_kmh * 60 + 0.5))
