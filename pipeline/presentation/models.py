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


class RankedListWidget(BaseModel):
    type: Literal["ranked_list"] = "ranked_list"
    id: str
    title: str
    subtitle: str | None = None
    items: list[RankedListItem]
    format: Literal["currency", "percentage", "number"]


Widget = Annotated[
    StatWidget | MatrixWidget | RankedListWidget,
    Field(discriminator="type"),
]


class AlertPresentation(BaseModel):
    schema_version: Literal[1] = 1
    widgets: list[Widget]

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)


def presentation_from_dict(data: dict) -> AlertPresentation:
    return AlertPresentation.model_validate(data)
