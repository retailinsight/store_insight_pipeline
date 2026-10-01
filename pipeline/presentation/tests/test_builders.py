"""Tests for the presentation builders."""
from __future__ import annotations

import json

from store_insight.pipeline.presentation import build_presentation
from store_insight.pipeline.presentation.builders.compliance import (
    build_compliance_presentation,
)
from store_insight.pipeline.presentation.builders.osa_store_actionable import (
    build_osa_store_actionable_presentation,
)
from store_insight.pipeline.presentation.models import (
    AlertPresentation,
    LineChartWidget,
    MatrixWidget,
    RankedListWidget,
    StatWidget,
)


def test_osa_store_actionable_includes_osa_stat_and_matrix():
    signal = {
        "signal_type": "OSA_STORE_ACTIONABLE",
        "facts": {
            "chain_store_this_week_osa": 94.0,
            "chain_store_last_week_osa": 93.5,
            "day_period_grid": [
                {
                    "date": "2026-09-18",
                    "day": "Friday",
                    "period_label": "Morning (Open-12pm)",
                    "total_osa_pct": 90.0,
                },
                {
                    "date": "2026-09-18",
                    "day": "Friday",
                    "period_label": "Afternoon (12pm-6pm)",
                    "total_osa_pct": 95.0,
                },
            ],
            "ppg_lsv_changes": [
                {
                    "ppg": "LAGER PREM CANS",
                    "latest_week_lsv": {"store_controlled": 104.6},
                },
            ],
            "item_lsv_changes": [
                {
                    "item_name": "STELLA ARTOIS CANS",
                    "eans": ["5014379012866"],
                    "upcs": [],
                    "latest_week_lsv": {"store_controlled": 75.44},
                },
            ],
        },
    }
    pres = build_osa_store_actionable_presentation(signal, {})
    assert pres.schema_version == 1
    assert any(w.id == "total_osa" for w in pres.widgets if isinstance(w, StatWidget))
    matrix = next(w for w in pres.widgets if isinstance(w, MatrixWidget))
    assert matrix.id == "day_period_grid"
    assert matrix.rows[0].label == "Friday"
    assert matrix.rows[0].date == "2026-09-18"
    ranked = [w for w in pres.widgets if isinstance(w, RankedListWidget)]
    assert [w.id for w in ranked] == ["ppg_lsv_changes", "item_lsv_changes"]
    assert ranked[0].items[0].value == 104.6
    assert ranked[1].items[0].secondary_label == "5014379012866"


def test_compliance_includes_line_chart_only():
    signal = {
        "signal_type": "COMPLIANCE",
        "facts": {
            "trailing_7d_tf": [
                {"date": "2026-09-18", "day": "Friday", "worked": 10, "tf_count": 10},
                {"date": "2026-09-19", "day": "Saturday", "worked": 4, "tf_count": 4},
            ],
        },
    }
    pres = build_compliance_presentation(signal, {})
    assert len(pres.widgets) == 1
    chart = pres.widgets[0]
    assert isinstance(chart, LineChartWidget)
    assert chart.id == "trailing_7d_tf"
    assert chart.categories[0].label == "Friday"
    assert chart.categories[0].date == "2026-09-18"
    assert len(chart.series) == 1
    assert chart.series[0].data == [10.0, 4.0]


def test_build_presentation_returns_model_for_known_signal():
    signal = {
        "signal_type": "OSA_STORE_ACTIONABLE",
        "facts": {"chain_store_this_week_osa": 94.0},
    }
    pres = build_presentation("OSA_STORE_ACTIONABLE", signal, {})
    assert isinstance(pres, AlertPresentation)


def test_build_presentation_returns_none_for_unknown_signal():
    assert build_presentation("UNKNOWN_TYPE", {"facts": {}}, {}) is None


def test_presentation_serialises_to_valid_json():
    signal = {
        "signal_type": "COMPLIANCE",
        "facts": {
            "alert_volume_by_day": [{"date": "2026-09-18", "generated": 10, "worked": 10}],
            "trailing_7d_tf": [],
            "tf_by_alert_type": [],
        },
    }
    pres = build_compliance_presentation(signal, {})
    raw = json.loads(pres.model_dump_json())
    assert raw["schema_version"] == 1
    assert all("type" in w for w in raw["widgets"])
