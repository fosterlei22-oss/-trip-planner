from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


TravelStyle = Literal["relaxed", "classic", "deep", "family", "foodie"]
BudgetLevel = Literal["economy", "standard", "comfort"]


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=40)
    days: int = Field(..., ge=1, le=14)
    people: int = Field(2, ge=1, le=12)
    budget_level: BudgetLevel = "standard"
    travel_style: TravelStyle = "classic"
    interests: list[str] = Field(default_factory=list, max_length=8)
    start_date: date | None = None
    notes: str = Field("", max_length=300)

    @field_validator("destination")
    @classmethod
    def normalize_destination(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("目的地不能为空")
        return cleaned

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class Place(BaseModel):
    name: str
    category: str
    description: str
    lat: float
    lng: float
    estimated_hours: float
    ticket: int = 0


class DayPlan(BaseModel):
    day: int
    theme: str
    morning: Place
    afternoon: Place
    evening: Place
    transport: str
    meals: list[str]
    estimated_cost: int
    teacher_note: str


class BudgetBreakdown(BaseModel):
    lodging: int
    food: int
    transport: int
    tickets: int
    misc: int
    total: int
    per_person: int


class TripPlan(BaseModel):
    title: str
    destination: str
    summary: str
    request: TripRequest
    days: list[DayPlan]
    budget: BudgetBreakdown
    route_points: list[Place]
    packing_list: list[str]
    tips: list[str]
