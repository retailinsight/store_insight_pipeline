"""
Pydantic reference models for the Overall + Availability KPI card ``details``
payloads.

Status
------
These models are **reference types only** — they are not currently wired into
any route as a ``response_model``. ``kpi_builder.get_kpis`` returns plain dicts
assembled from the JSON columns ``OVERALL_DETAILS_JSON`` and
``AVAILABILITY_DETAILS_JSON`` in ``KPI_AVAILABILITY_SUMMARY``; the dict shape is
expected to match ``OverallDetails`` / ``AvailabilityDetails`` below.

Note the live API response envelope is ``{"data": [...], "meta": {...}}`` — the
``KPIResponse`` model in this file predates that change and does not reflect it.
Kept here so the intended per-field types of the JSON blobs are documented.
"""

from typing import List, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class TrendBlock(BaseModel):
    value: str
    trend_direction: str
    trend: str


class PerformanceBreakdownOverall(BaseModel):
    current_week: str
    last_week: str
    month_average: str
    year_average: str


class OverallDetails(BaseModel):
    target: TrendBlock
    previous_average: TrendBlock
    performance_breakdown: PerformanceBreakdownOverall
    Key_insights: List[str]


# ---------------------------------------------------------------------------
# Availability KPI
# ---------------------------------------------------------------------------

class AvailabilityPerformanceBreakdown(BaseModel):
    actionability: str
    Alert_compliance: str
    tick_flick: str


class TopDriver(BaseModel):
    driver: str
    Subcategory: str
    When: str
    trend_direction: str
    trend: str


class CategoryPerformance(BaseModel):
    category: str
    performance: str
    warning: bool


class TimePeriodPerformance(BaseModel):
    time_period: str
    performance: str
    rag_status: str


class DayPerformance(BaseModel):
    day: str
    performance: List[TimePeriodPerformance]


class AvailabilityDetails(BaseModel):
    performance_breakdown: AvailabilityPerformanceBreakdown
    summary: str
    top_drivers: List[TopDriver]
    category_performance: List[CategoryPerformance]
    time_of_day_analysis: List[DayPerformance]


# ---------------------------------------------------------------------------
# Top-level KPI cards
# ---------------------------------------------------------------------------

class OverallKPI(BaseModel):
    id: str
    name: str
    value: str
    trend_direction: str
    trend: str
    cluster_average: str
    details: OverallDetails


class AvailabilityKPI(BaseModel):
    id: str
    name: str
    value: str
    trend_direction: str
    trend: str
    cluster_average: str
    details: AvailabilityDetails


class KPIResponse(BaseModel):
    kpis: List[OverallKPI | AvailabilityKPI]
