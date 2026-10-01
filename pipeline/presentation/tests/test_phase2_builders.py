"""Acceptance tests for the Phase 2 presentation builders.

These tests exercise the five remaining fallback signal types now that Imran has
confirmed the widget shapes in `docs/presentation-phase2-design.md`.
"""
from __future__ import annotations

import json

from store_insight.pipeline.presentation.builders.markdown_override import (
    build_markdown_override_presentation,
)
from store_insight.pipeline.presentation.builders.markdown_sku import (
    build_markdown_sku_presentation,
)
from store_insight.pipeline.presentation.builders.osa_big_drop import (
    build_osa_big_drop_presentation,
)
from store_insight.pipeline.presentation.builders.osa_recurring_slot import (
    build_osa_recurring_slot_presentation,
)
from store_insight.pipeline.presentation.builders.prompted_markdown_compliance import (
    build_prompted_markdown_compliance_presentation,
)


# -----------------------------------------------------------------------------
# PROMPTED_MARKDOWN_COMPLIANCE
# -----------------------------------------------------------------------------
PROMPTED_MARKDOWN_COMPLIANCE_SIGNAL = {
    "signal_type": "PROMPTED_MARKDOWN_COMPLIANCE",
    "this_week_compliance_rate": 73.41,
    "wow_change_pp": -1.4,
    "facts": {
        "daily_performance_last_7d": [
            {"date": "2026-09-21", "day": "Monday", "compliance_pct": 65.17, "checks_due": 290, "actioned_on_time": 189},
            {"date": "2026-09-22", "day": "Tuesday", "compliance_pct": 82.2, "checks_due": 309, "actioned_on_time": 254},
            {"date": "2026-09-23", "day": "Wednesday", "compliance_pct": 44.49, "checks_due": 472, "actioned_on_time": 210},
            {"date": "2026-09-24", "day": "Thursday", "compliance_pct": 74.48, "checks_due": 482, "actioned_on_time": 359},
            {"date": "2026-09-25", "day": "Friday", "compliance_pct": 75.33, "checks_due": 300, "actioned_on_time": 226},
            {"date": "2026-09-26", "day": "Saturday", "compliance_pct": 100.0, "checks_due": 329, "actioned_on_time": 329},
            {"date": "2026-09-27", "day": "Sunday", "compliance_pct": 90.95, "checks_due": 199, "actioned_on_time": 181},
        ],
        "worst_departments_top3": [
            {"dept": "MEAT PRODUCTS", "prompts": 5, "actioned_on_time": 1, "compliance_pct": 20.0},
            {"dept": "BREAKFAST CEREALS", "prompts": 45, "actioned_on_time": 10, "compliance_pct": 22.22},
            {"dept": "BEER/LAGER & CIDER", "prompts": 87, "actioned_on_time": 21, "compliance_pct": 24.14},
        ],
    },
}

PROMPTED_MARKDOWN_COMPLIANCE_EXPECTED = {
    "schema_version": 1,
    "widgets": [
        {
            "type": "stat",
            "id": "this_week_compliance_rate",
            "title": "On-time compliance",
            "value": 73.41,
            "format": "percentage",
        },
        {
            "type": "stat",
            "id": "wow_change_pp",
            "title": "Change vs last week",
            "value": -1.4,
            "format": "number",
        },
        {
            "type": "line_chart",
            "id": "daily_compliance",
            "title": "On-time compliance by day",
            "subtitle": "Last 7 days",
            "categories": [
                {"label": "Monday", "date": "2026-09-21"},
                {"label": "Tuesday", "date": "2026-09-22"},
                {"label": "Wednesday", "date": "2026-09-23"},
                {"label": "Thursday", "date": "2026-09-24"},
                {"label": "Friday", "date": "2026-09-25"},
                {"label": "Saturday", "date": "2026-09-26"},
                {"label": "Sunday", "date": "2026-09-27"},
            ],
            "series": [
                {
                    "name": "On-time compliance %",
                    "data": [65.17, 82.2, 44.49, 74.48, 75.33, 100.0, 90.95],
                }
            ],
            "format": "percentage",
        },
        {
            "type": "ranked_list",
            "id": "worst_departments",
            "title": "Worst departments",
            "subtitle": "By on-time compliance %",
            "items": [
                {"label": "MEAT PRODUCTS", "value": 20.0, "secondary_label": "1/5"},
                {"label": "BREAKFAST CEREALS", "value": 22.22, "secondary_label": "10/45"},
                {"label": "BEER/LAGER & CIDER", "value": 24.14, "secondary_label": "21/87"},
            ],
            "format": "percentage",
        },
    ],
}


def test_prompted_markdown_compliance_presentation():
    pres = build_prompted_markdown_compliance_presentation(PROMPTED_MARKDOWN_COMPLIANCE_SIGNAL, {})
    assert json.loads(pres.model_dump_json()) == PROMPTED_MARKDOWN_COMPLIANCE_EXPECTED


# -----------------------------------------------------------------------------
# OSA_BIG_DROP
# -----------------------------------------------------------------------------
OSA_BIG_DROP_SIGNAL = {
    "signal_type": "OSA_BIG_DROP",
    "this_week_osa": 89.14,
    "wow_drift_pp": -10.86,
    "facts": {
        "day_period_grid": [
            {"date": "2026-09-21", "day": "Monday", "period_label": "Morning (Open-12pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-21", "day": "Monday", "period_label": "Afternoon (12pm-6pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-21", "day": "Monday", "period_label": "Evening (6pm-Close)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-22", "day": "Tuesday", "period_label": "Morning (Open-12pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-22", "day": "Tuesday", "period_label": "Afternoon (12pm-6pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-22", "day": "Tuesday", "period_label": "Evening (6pm-Close)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-23", "day": "Wednesday", "period_label": "Morning (Open-12pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-23", "day": "Wednesday", "period_label": "Afternoon (12pm-6pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-23", "day": "Wednesday", "period_label": "Evening (6pm-Close)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-24", "day": "Thursday", "period_label": "Morning (Open-12pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-24", "day": "Thursday", "period_label": "Afternoon (12pm-6pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-24", "day": "Thursday", "period_label": "Evening (6pm-Close)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-25", "day": "Friday", "period_label": "Morning (Open-12pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-25", "day": "Friday", "period_label": "Afternoon (12pm-6pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-25", "day": "Friday", "period_label": "Evening (6pm-Close)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-26", "day": "Saturday", "period_label": "Morning (Open-12pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-26", "day": "Saturday", "period_label": "Afternoon (12pm-6pm)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-26", "day": "Saturday", "period_label": "Evening (6pm-Close)", "store_controlled_lsv": 0.0},
            {"date": "2026-09-27", "day": "Sunday", "period_label": "Morning (Open-12pm)", "store_controlled_lsv": 27.16},
            {"date": "2026-09-27", "day": "Sunday", "period_label": "Afternoon (12pm-6pm)", "store_controlled_lsv": 1.81},
            {"date": "2026-09-27", "day": "Sunday", "period_label": "Evening (6pm-Close)", "store_controlled_lsv": 0.0},
        ],
        "ppg_lsv": [
            {"ppg": "HAND ROLLING TOBACCO", "store_controlled_lsv": 28.97},
        ],
        "item_lsv_changes": [
            {
                "item_code": "2296",
                "item_name": "GOLDEN VIRGINIA THE ORIGI",
                "ppg": "HAND ROLLING TOBACCO",
                "upcs": ["5000435010778"],
                "eans": ["5000435010778"],
                "identifier_mapping_status": "unique",
                "latest_week_lsv": {"total": 28.97, "store_controlled": 28.97, "upstream": 0.0, "unknown": 0.0},
            },
        ],
    },
}

OSA_BIG_DROP_EXPECTED = {
    "schema_version": 1,
    "widgets": [
        {
            "type": "stat",
            "id": "this_week_osa",
            "title": "OSA on drop day",
            "value": 89.14,
            "format": "percentage",
        },
        {
            "type": "stat",
            "id": "osa_drop_pp",
            "title": "OSA drop",
            "value": -10.86,
            "format": "number",
        },
        {
            "type": "matrix",
            "id": "day_period_grid",
            "title": "Lost sales by day and period",
            "subtitle": None,
            "columns": [
                {"key": "morning", "label": "Morning"},
                {"key": "afternoon", "label": "Afternoon"},
                {"key": "evening", "label": "Evening"},
            ],
            "rows": [
                {"label": "Monday", "date": "2026-09-21", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
                {"label": "Tuesday", "date": "2026-09-22", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
                {"label": "Wednesday", "date": "2026-09-23", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
                {"label": "Thursday", "date": "2026-09-24", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
                {"label": "Friday", "date": "2026-09-25", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
                {"label": "Saturday", "date": "2026-09-26", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
                {"label": "Sunday", "date": "2026-09-27", "values": {"morning": 27.16, "afternoon": 1.81, "evening": 0.0}},
            ],
            "format": "currency",
        },
        {
            "type": "ranked_list",
            "id": "ppg_lsv",
            "title": "Worst performing PPGs",
            "subtitle": "Store-controlled lost sales this week",
            "items": [{"label": "HAND ROLLING TOBACCO", "value": 28.97, "secondary_label": None}],
            "format": "currency",
        },
        {
            "type": "ranked_list",
            "id": "item_lsv_changes",
            "title": "Worst performing items",
            "subtitle": "Store-controlled lost sales this week",
            "items": [
                {"label": "GOLDEN VIRGINIA THE ORIGI", "value": 28.97, "secondary_label": "5000435010778"}
            ],
            "format": "currency",
        },
    ],
}


def test_osa_big_drop_presentation():
    pres = build_osa_big_drop_presentation(OSA_BIG_DROP_SIGNAL, {})
    assert json.loads(pres.model_dump_json()) == OSA_BIG_DROP_EXPECTED


# -----------------------------------------------------------------------------
# OSA_RECURRING_SLOT
# -----------------------------------------------------------------------------
OSA_RECURRING_SLOT_SIGNAL = {
    "signal_type": "OSA_RECURRING_SLOT",
    "total_lsv": 94.01,
    "avg_weekly_lsv": 16.79,
    "repeat_item_details": [
        {"item_code": "29355", "item_description": "CP WHITE PARISIAN", "repeat_weeks": 8, "total_lsv": 35.17, "avg_weekly_lsv": 4.4},
        {"item_code": "29810", "item_description": "CP SAUSAGE ROLLS", "repeat_weeks": 4, "total_lsv": 31.05, "avg_weekly_lsv": 7.76},
        {"item_code": "29348", "item_description": "CP CHEESE TWIST", "repeat_weeks": 6, "total_lsv": 27.79, "avg_weekly_lsv": 4.63},
    ],
    "facts": {
        "slot_history": [
            {"year": 2026, "week": 35, "sales": 51.0, "lsv_vol": 4.0033, "lsv": 7.25, "osa_pct": 92.72},
            {"year": 2026, "week": 36, "sales": 51.0, "lsv_vol": 10.7321, "lsv": 13.0, "osa_pct": 82.62},
            {"year": 2026, "week": 37, "sales": 50.0, "lsv_vol": 5.7358, "lsv": 7.6, "osa_pct": 89.71},
            {"year": 2026, "week": 38, "sales": 8.0, "lsv_vol": 45.1482, "lsv": 56.85, "osa_pct": 15.05},
            {"year": 2026, "week": 39, "sales": 5.0, "lsv_vol": 37.549, "lsv": 45.86, "osa_pct": 11.75},
        ],
    },
}

OSA_RECURRING_SLOT_EXPECTED = {
    "schema_version": 1,
    "widgets": [
        {
            "type": "stat",
            "id": "total_lsv",
            "title": "Total lost sales (10 weeks)",
            "value": 94.01,
            "format": "currency",
        },
        {
            "type": "stat",
            "id": "avg_weekly_lsv",
            "title": "Average weekly lost sales",
            "value": 16.79,
            "format": "currency",
        },
        {
            "type": "line_chart",
            "id": "slot_lsv_history",
            "title": "Slot lost sales history",
            "subtitle": "Last 10 weeks",
            "categories": [
                {"label": "2026-W35", "date": None},
                {"label": "2026-W36", "date": None},
                {"label": "2026-W37", "date": None},
                {"label": "2026-W38", "date": None},
                {"label": "2026-W39", "date": None},
            ],
            "series": [{"name": "Lost sales value", "data": [7.25, 13.0, 7.6, 56.85, 45.86]}],
            "format": "currency",
        },
        {
            "type": "line_chart",
            "id": "slot_osa_history",
            "title": "Slot OSA history",
            "subtitle": "Last 10 weeks",
            "categories": [
                {"label": "2026-W35", "date": None},
                {"label": "2026-W36", "date": None},
                {"label": "2026-W37", "date": None},
                {"label": "2026-W38", "date": None},
                {"label": "2026-W39", "date": None},
            ],
            "series": [{"name": "OSA %", "data": [92.72, 82.62, 89.71, 15.05, 11.75]}],
            "format": "percentage",
        },
        {
            "type": "ranked_list",
            "id": "recurring_items",
            "title": "Recurring items",
            "subtitle": "Lost sales over repeated weeks",
            "items": [
                {"label": "CP WHITE PARISIAN", "value": 35.17, "secondary_label": "29355"},
                {"label": "CP SAUSAGE ROLLS", "value": 31.05, "secondary_label": "29810"},
                {"label": "CP CHEESE TWIST", "value": 27.79, "secondary_label": "29348"},
            ],
            "format": "currency",
        },
    ],
}


def test_osa_recurring_slot_presentation():
    pres = build_osa_recurring_slot_presentation(OSA_RECURRING_SLOT_SIGNAL, {})
    assert json.loads(pres.model_dump_json()) == OSA_RECURRING_SLOT_EXPECTED


# -----------------------------------------------------------------------------
# MARKDOWN_OVERRIDE
# -----------------------------------------------------------------------------
MARKDOWN_OVERRIDE_SIGNAL = {
    "signal_type": "MARKDOWN_OVERRIDE",
    "this_week_override_rate": 5.67,
    "wow_change_pp": 5.67,
    "facts": {
        "override_dept_breakdown": [
            {"dept": "INTERNATIONAL", "total_markdowns": 15, "overrides": 6, "override_rate_pct": 40.0},
            {"dept": "CANNED & DRIED VEGETABLES", "total_markdowns": 9, "overrides": 4, "override_rate_pct": 44.44},
            {"dept": "CANNED FISH", "total_markdowns": 4, "overrides": 2, "override_rate_pct": 50.0},
        ],
    },
}

MARKDOWN_OVERRIDE_EXPECTED = {
    "schema_version": 1,
    "widgets": [
        {
            "type": "stat",
            "id": "this_week_override_rate",
            "title": "Override rate this week",
            "value": 5.67,
            "format": "percentage",
        },
        {
            "type": "stat",
            "id": "wow_change_pp",
            "title": "Change vs last week",
            "value": 5.67,
            "format": "number",
        },
        {
            "type": "ranked_list",
            "id": "override_departments",
            "title": "Departments by override rate",
            "subtitle": None,
            "items": [
                {"label": "CANNED FISH", "value": 50.0, "secondary_label": "2/4"},
                {"label": "CANNED & DRIED VEGETABLES", "value": 44.44, "secondary_label": "4/9"},
                {"label": "INTERNATIONAL", "value": 40.0, "secondary_label": "6/15"},
            ],
            "format": "percentage",
        },
    ],
}


def test_markdown_override_presentation():
    pres = build_markdown_override_presentation(MARKDOWN_OVERRIDE_SIGNAL, {})
    assert json.loads(pres.model_dump_json()) == MARKDOWN_OVERRIDE_EXPECTED


# -----------------------------------------------------------------------------
# MARKDOWN_SKU
# -----------------------------------------------------------------------------
MARKDOWN_SKU_SIGNAL = {
    "signal_type": "MARKDOWN_SKU",
    "avg_markdown_pct": 29.64,
    "markdown_request_count": 14,
    "facts": {
        "sku_markdown_history": [
            {"week_start": "2026-08-24", "request_count": 1, "override_count": 0, "avg_markdown_pct": 31.0},
            {"week_start": "2026-08-31", "request_count": 3, "override_count": 0, "avg_markdown_pct": 30.0},
            {"week_start": "2026-09-07", "request_count": 3, "override_count": 0, "avg_markdown_pct": 29.33},
            {"week_start": "2026-09-14", "request_count": 4, "override_count": 0, "avg_markdown_pct": 29.5},
            {"week_start": "2026-09-21", "request_count": 3, "override_count": 0, "avg_markdown_pct": 29.33},
        ],
    },
}

MARKDOWN_SKU_EXPECTED = {
    "schema_version": 1,
    "widgets": [
        {
            "type": "stat",
            "id": "avg_markdown_pct",
            "title": "Average markdown depth",
            "value": 29.64,
            "format": "percentage",
        },
        {
            "type": "stat",
            "id": "markdown_request_count",
            "title": "Markdown requests (last 5 weeks)",
            "value": 14,
            "format": "number",
        },
        {
            "type": "line_chart",
            "id": "request_history",
            "title": "Weekly markdown requests",
            "subtitle": None,
            "categories": [
                {"label": "2026-08-24", "date": "2026-08-24"},
                {"label": "2026-08-31", "date": "2026-08-31"},
                {"label": "2026-09-07", "date": "2026-09-07"},
                {"label": "2026-09-14", "date": "2026-09-14"},
                {"label": "2026-09-21", "date": "2026-09-21"},
            ],
            "series": [{"name": "Requests", "data": [1, 3, 3, 4, 3]}],
            "format": "number",
        },
        {
            "type": "line_chart",
            "id": "avg_markdown_history",
            "title": "Weekly average markdown depth",
            "subtitle": None,
            "categories": [
                {"label": "2026-08-24", "date": "2026-08-24"},
                {"label": "2026-08-31", "date": "2026-08-31"},
                {"label": "2026-09-07", "date": "2026-09-07"},
                {"label": "2026-09-14", "date": "2026-09-14"},
                {"label": "2026-09-21", "date": "2026-09-21"},
            ],
            "series": [{"name": "Avg markdown %", "data": [31.0, 30.0, 29.33, 29.5, 29.33]}],
            "format": "percentage",
        },
    ],
}


def test_markdown_sku_presentation():
    pres = build_markdown_sku_presentation(MARKDOWN_SKU_SIGNAL, {})
    assert json.loads(pres.model_dump_json()) == MARKDOWN_SKU_EXPECTED
