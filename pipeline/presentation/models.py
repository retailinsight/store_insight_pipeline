"""Typed widget contract for the API/UI.

This is the single source of truth for what a smart-action card displays.
The API passes the payload through untouched; the UI renders by widget type.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class StatWidget(BaseModel):
    type: Literal["stat"] = "stat"
    id: str
    title: str
    value: float
    format: Literal["currency", "percentage", "number"]


class MatrixColumn(BaseModel):
    key: str
    label: str


class MatrixRow(BaseModel):
    label: str
    date: str | None = None
    values: dict[str, float]


class MatrixWidget(BaseModel):
    type: Literal["matrix"] = "matrix"
    id: str
    title: str
    subtitle: str | None = None
    columns: list[MatrixColumn]
    rows: list[MatrixRow]
    format: Literal["currency", "percentage", "number"]


class RankedListItem(BaseModel):
    label: str
    value: float
    secondary_label: str | None = None


class RankedListWidget(BaseModel):
    type: Literal["ranked_list"] = "ranked_list"
    id: str
    title: str
    subtitle: str | None = None
    items: list[RankedListItem]
    format: Literal["currency", "percentage", "number"]


class ChartCategory(BaseModel):
    label: str
    date: str | None = None


class ChartSeries(BaseModel):
    name: str
    data: list[float]


class BarChartWidget(BaseModel):
    type: Literal["bar_chart"] = "bar_chart"
    id: str
    title: str
    subtitle: str | None = None
    categories: list[ChartCategory]
    series: list[ChartSeries]
    format: Literal["currency", "percentage", "number"]
    highlighted_index: int | None = None


class LineChartWidget(BaseModel):
    type: Literal["line_chart"] = "line_chart"
    id: str
    title: str
    subtitle: str | None = None
    categories: list[ChartCategory]
    series: list[ChartSeries]
    format: Literal["currency", "percentage", "number"]


Widget = Annotated[
    StatWidget | MatrixWidget | RankedListWidget | BarChartWidget | LineChartWidget,
    Field(discriminator="type"),
]


class AlertPresentation(BaseModel):
    schema_version: Literal[1] = 1
    widgets: list[Widget]

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)


def presentation_from_dict(data: dict) -> AlertPresentation:
    return AlertPresentation.model_validate(data)
