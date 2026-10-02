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
            "type": "bar_chart",
            "id": "daily_compliance_bar",
            "title": "Compliance % — last 7 days",
            "subtitle": "Performance by day — last 7 days",
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
                    "name": "Compliance %",
                    "data": [65.17, 82.2, 44.49, 74.48, 75.33, 100.0, 90.95],
                }
            ],
            "format": "percentage",
            "highlighted_index": None,
        },
        {
            "type": "line_chart",
            "id": "checks_due_vs_actioned",
            "title": "Checks due vs actioned on time — last 7 days",
            "subtitle": "Performance by day — last 7 days",
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
                    "name": "Checks due",
                    "data": [290.0, 309.0, 472.0, 482.0, 300.0, 329.0, 199.0],
                },
                {
                    "name": "Actioned on time",
                    "data": [189.0, 254.0, 210.0, 359.0, 226.0, 329.0, 181.0],
                },
            ],
            "format": "number",
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
    "latest_day": "Thursday",
    "this_week_lsv": {"total": 28.97, "store_controlled": 28.97, "upstream": 0.0, "unknown": 0.0},
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
            "id": "lost_sales_on_drop_day",
            "title": "Lost sales on Thursday",
            "value": 28.97,
            "format": "currency",
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
    "dow_name": "Wednesday",
    "period_label": "Evening (6pm-12am)",
    "repeat_item_details": [
        {"item_code": "29355", "item_description": "CP WHITE PARISIAN", "repeat_weeks": 8, "total_lsv": 35.17, "avg_weekly_lsv": 4.4},
        {"item_code": "29810", "item_description": "CP SAUSAGE ROLLS", "repeat_weeks": 4, "total_lsv": 31.05, "avg_weekly_lsv": 7.76},
        {"item_code": "29348", "item_description": "CP CHEESE TWIST", "repeat_weeks": 6, "total_lsv": 27.79, "avg_weekly_lsv": 4.63},
    ],
    "facts": {
        "item_identifiers": {
            "29355": {"upc": "5000000000001", "ean": None},
            "29810": {"upc": "5000000000002", "ean": None},
            "29348": {"upc": "5000000000003", "ean": None},
        },
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
            "title": "Total lost sales",
            "value": 94.01,
            "format": "currency",
        },
        {
            "type": "line_chart",
            "id": "slot_lsv_history",
            "title": "Wednesday evening lost sales",
            "subtitle": "Last 10 weeks",
            "categories": [
                {"label": "W35", "date": "2026-08-24"},
                {"label": "W36", "date": "2026-08-31"},
                {"label": "W37", "date": "2026-09-07"},
                {"label": "W38", "date": "2026-09-14"},
                {"label": "W39", "date": "2026-09-21"},
            ],
            "series": [{"name": "Lost sales value", "data": [7.25, 13.0, 7.6, 56.85, 45.86]}],
            "format": "currency",
        },
        {
            "type": "line_chart",
            "id": "slot_osa_history",
            "title": "Wednesday evening OSA",
            "subtitle": "Last 10 weeks",
            "categories": [
                {"label": "W35", "date": "2026-08-24"},
                {"label": "W36", "date": "2026-08-31"},
                {"label": "W37", "date": "2026-09-07"},
                {"label": "W38", "date": "2026-09-14"},
                {"label": "W39", "date": "2026-09-21"},
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
                {"label": "CP WHITE PARISIAN", "value": 35.17, "secondary_label": "5000000000001"},
                {"label": "CP SAUSAGE ROLLS", "value": 31.05, "secondary_label": "5000000000002"},
                {"label": "CP CHEESE TWIST", "value": 27.79, "secondary_label": "5000000000003"},
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
            "title": "Worst performing departments",
            "subtitle": "INTERNATIONAL: 9 of 15 compliant (60.0%)",
            "items": [
                {"label": "INTERNATIONAL", "value": 60.0, "secondary_label": "9 out of 15 compliant"},
                {"label": "CANNED & DRIED VEGETABLES", "value": 55.56, "secondary_label": "5 out of 9 compliant"},
                {"label": "CANNED FISH", "value": 50.0, "secondary_label": "2 out of 4 compliant"},
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
