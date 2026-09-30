"""Generate BINNED_WASTE_TREND/SPIKE alerts for a single analysis date and save locally.

Loads only the source data needed for the new detectors, runs detection → facts
→ narratives → presentation → scoring, and writes a JSON file to the local
working directory.

Usage:
    python scripts/run_binned_waste_alerts_local.py 2026-09-27
    python scripts/run_binned_waste_alerts_local.py 2026-09-27 --database STORE_INSIGHT_DB

Output:
    binned_waste_alerts_<analysis_date>.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

from snowflake.snowpark import functions as F

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORKSPACE))

from snowflake_credentials import get_credentials  # noqa: E402
from store_insight.pipeline.config.loader import load_config  # noqa: E402
from store_insight.pipeline.pipeline.pipeline import _make_alert_id  # noqa: E402
from store_insight.pipeline.pipeline.session import create_session  # noqa: E402
from store_insight.pipeline.presentation import build_presentation  # noqa: E402
from store_insight.pipeline.stages._1_detect.detectors.binned_waste import (  # noqa: E402
    spike,
    trend,
)
from store_insight.pipeline.stages._2_score.score import score_all  # noqa: E402
from store_insight.pipeline.stages._3_facts.gatherers import (  # noqa: E402
    binned_waste_spike_facts,
    binned_waste_trend_facts,
)
from store_insight.pipeline.stages._4_investigate import rule_based  # noqa: E402


def _session(database: str, schema: str):
    params = get_credentials().get_connection_params()
    os.environ.setdefault("SNOWFLAKE_ACCOUNT", params["account"])
    os.environ.setdefault("SNOWFLAKE_USER", params["user"])
    if params.get("password"):
        os.environ.setdefault("SNOWFLAKE_PASSWORD", params["password"])
    os.environ["SNOWFLAKE_ROLE"] = "STORE_INSIGHT_ROLE"
    os.environ.setdefault("SNOWFLAKE_WAREHOUSE", params.get("warehouse", "STORE_INSIGHT_WH"))
    os.environ["SNOWFLAKE_DATABASE"] = database
    os.environ["SNOWFLAKE_SCHEMA"] = schema
    cfg = {
        "connection": {
            "database": database,
            "schema_name": schema,
            "role": "STORE_INSIGHT_ROLE",
            "warehouse": params.get("warehouse", "STORE_INSIGHT_WH"),
        }
    }
    return create_session(cfg)


def _table(session, database: str, schema: str, name: str):
    return session.table(f"{database}.{schema}.{name}")


def _load_sources(session, analysis_date: datetime.date, database: str, schema: str, store_ids: list[int] | None = None):
    """Load only the tables/columns needed for binned-waste alerts."""
    start = (analysis_date - datetime.timedelta(days=20)).isoformat()
    end = analysis_date.isoformat()

    wastage = (
        _table(session, database, schema, "WASTAGE_V1")
        .filter(
            (F.col("DATE") >= start) &
            (F.col("DATE") <= end) &
            F.col("STORE_ID").is_not_null() &
            F.col("UPC").is_not_null() &
            F.col("WASTE_QUANTITY").is_not_null() &
            F.col("ORIGINAL_PRICE").is_not_null()
        )
        .select("STORE_ID", "UPC", "DATE", "WASTE_QUANTITY", "ORIGINAL_PRICE", "WASTE_REASON")
    )
    if store_ids:
        wastage = wastage.filter(F.col("STORE_ID").isin(store_ids))

    store_hierarchy = (
        _table(session, database, schema, "STORE_HIERARCHY_V1")
        .select("STORE_ID", "STORE_NAME")
    )
    if store_ids:
        store_hierarchy = store_hierarchy.filter(F.col("STORE_ID").isin(store_ids))

    item_hierarchy = (
        _table(session, database, schema, "WMD_HIERARCHY_V1")
        .select("UPC", "ITEM_DESCRIPTION", "ITEM_HIERARCHY_2")
    )

    # Prompted compliance may not exist in some environments; guard gracefully.
    try:
        prompted = (
            _table(session, database, schema, "PROMPTED_COMPLIANCE_V1")
            .filter(
                (F.col("ALERT_DATE") >= start) &
                (F.col("ALERT_DATE") <= end)
            )
            .select("ALERT_DATE", "STORE_ID", "ITEM_HIERARCHY_2", "COMPLIANT")
        )
        if store_ids:
            prompted = prompted.filter(F.col("STORE_ID").isin(store_ids))
    except Exception as exc:
        print(f"[warn] PROMPTED_COMPLIANCE_V1 not available: {exc}")
        prompted = None

    return wastage, store_hierarchy, item_hierarchy, prompted


def _build_card(signal, facts, narrative, presentation_json, analysis_date, cfg):
    sort_value = signal.get("score", 0.0)
    alert_id = _make_alert_id(cfg, signal, analysis_date.isoformat())
    signal_json = {k: v for k, v in signal.items() if k != "facts"}
    return {
        "alert_id": alert_id,
        "signal_id": alert_id,
        "analysis_date": analysis_date.isoformat(),
        "run_date": datetime.date.today().isoformat(),
        "alert_type": signal["signal_type"],
        "store_id": signal["store_id"],
        "section": signal.get("department") or "",
        "type": "Waste",
        "trigger_types": signal["trigger_types"],
        "issue": narrative["issue"],
        "explanation": narrative["explanation"],
        "cost_if_not_fixed": narrative["cost_if_not_fixed"],
        "recommended_action": narrative["recommended_action"],
        "sort_value": sort_value,
        "signal_json": signal_json,
        "facts_json": facts,
        "presentation_json": presentation_json,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate binned-waste alerts locally")
    parser.add_argument(
        "analysis_date",
        nargs="?",
        default=(datetime.date.today() - datetime.timedelta(days=1)).isoformat(),
        help="Analysis date (YYYY-MM-DD). Defaults to yesterday.",
    )
    parser.add_argument(
        "--database",
        default="STORE_INSIGHT_DEV",
        help="Snowflake database containing the *_V1 views (default: STORE_INSIGHT_DEV).",
    )
    parser.add_argument(
        "--schema",
        default="PUBLIC",
        help="Snowflake schema containing the *_V1 views (default: PUBLIC).",
    )
    parser.add_argument(
        "--store-id",
        type=int,
        nargs="+",
        default=None,
        help="Optional: restrict to one or more store IDs (space-separated).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Output JSON path. Defaults to binned_waste_alerts_<analysis_date>.json",
    )
    args = parser.parse_args()

    analysis_date = datetime.date.fromisoformat(args.analysis_date)
    store_ids = args.store_id
    cfg = load_config("eastofengland")

    print(f"Running binned-waste alerts for analysis date {analysis_date.isoformat()}")
    print(f"Source database: {args.database}.{args.schema}")
    if store_ids:
        print(f"Store filter: {store_ids}")
    session = _session(args.database, args.schema)
    try:
        wastage, store_hierarchy, item_hierarchy, prompted = _load_sources(
            session, analysis_date, args.database, args.schema, store_ids
        )

        print("Running detectors...")
        trend_signals = trend.detect(
            wastage,
            store_hierarchy,
            analysis_date.isoformat(),
            store_id=store_ids,
        )
        spike_signals = spike.detect(
            wastage,
            store_hierarchy,
            analysis_date.isoformat(),
            store_id=store_ids,
        )
        all_signals = trend_signals + spike_signals
        print(f"  Trend signals: {len(trend_signals)}")
        print(f"  Spike signals: {len(spike_signals)}")

        if not all_signals:
            print("No binned-waste alerts generated.")
            return

        print("Scoring signals...")
        this_week_start = (analysis_date - datetime.timedelta(days=6)).isoformat()
        this_week_end = analysis_date.isoformat()
        score_all(
            all_signals,
            this_week_start=this_week_start,
            this_week_end=this_week_end,
            score_weights=cfg.scoring.score_weights if cfg and cfg.scoring else None,
            scoring_cfg=cfg.scoring if cfg and cfg.scoring else None,
        )

        print("Gathering facts...")
        trend_facts = binned_waste_trend_facts.gather(
            wastage=wastage,
            prompted_compliance=prompted,
            item_hierarchy=item_hierarchy,
            signals=trend_signals,
            this_week_end=analysis_date.isoformat(),
            top_n=5,
        )
        spike_facts = binned_waste_spike_facts.gather(
            wastage=wastage,
            prompted_compliance=prompted,
            item_hierarchy=item_hierarchy,
            signals=spike_signals,
            this_week_end=analysis_date.isoformat(),
            top_n=5,
        )
        facts_by_store = {**trend_facts, **spike_facts}

        cards = []
        for signal in all_signals:
            signal["facts"] = facts_by_store.get(signal["store_id"], {})
            narrative = rule_based.generate(signal)
            presentation = build_presentation(signal["signal_type"], signal, narrative)
            presentation_json = presentation.model_dump_json(by_alias=True) if presentation else None
            cards.append(_build_card(signal, signal["facts"], narrative, presentation_json, analysis_date, cfg))

        cards.sort(key=lambda c: c["sort_value"], reverse=True)

        output_path = Path(args.output_json or f"binned_waste_alerts_{analysis_date.isoformat()}.json")
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(cards, f, indent=2, default=str)
        print(f"Saved {len(cards)} alert(s) to {output_path.resolve()}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
