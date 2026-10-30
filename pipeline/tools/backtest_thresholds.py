"""
Backtest threshold changes against a subset of stores.

This CLI wraps the in-memory experiment runner
(``pipeline/tools/experiment_runner.py``) so threshold changes can be evaluated
without running the full store base or writing to the production output table.

Usage
-----
    # Compare current config vs proposed threshold overrides on three stores
    python pipeline/tools/backtest_thresholds.py \
        --client eastofengland \
        --analysis-date 2026-07-17 \
        --store-ids 508,492,641 \
        --proposed-config proposed_thresholds.yaml \
        --output report.json

    # Single variant run (proposed only) for one store and one signal type
    python pipeline/tools/backtest_thresholds.py \
        --client eastofengland \
        --analysis-date 2026-07-17 \
        --store-ids 508 \
        --signal-types OSA \
        --variant proposed \
        --proposed-config proposed_thresholds.yaml

The ``proposed-config`` YAML should contain a partial ``detector_config.thresholds``
structure, for example:

    detector_config:
      thresholds:
        OSA:
          min_wow_drop: 0.15
          min_chain_gap: 0.12
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from snowflake.snowpark import Session

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_PIPELINE_DIR = _HERE.parent

from store_insight.pipeline.config.loader import load_config  # noqa: E402
from store_insight.pipeline.config.models import PipelineConfig  # noqa: E402
from store_insight.pipeline.tools.experiment_runner import run_experiment  # noqa: E402

_ENV_PATH = _PIPELINE_DIR / ".env"


# ---------------------------------------------------------------------------
# Environment / session
# ---------------------------------------------------------------------------


def _load_env() -> None:
    """Load pipeline/.env into os.environ if it exists."""
    if not _ENV_PATH.exists():
        return
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _create_session() -> Session:
    """Create a Snowpark session from the same env vars used by deploy.py."""
    password = os.environ.get("SNOWFLAKE_PASSWORD")
    params = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": os.environ["SNOWFLAKE_SCHEMA"],
    }
    if password:
        params["password"] = password
    else:
        params["authenticator"] = "externalbrowser"
    return Session.builder.configs(params).create()


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _parse_store_ids(value: str) -> list[int]:
    """Parse a comma-separated store ID list."""
    return [int(s.strip()) for s in value.split(",") if s.strip()]


def _load_store_ids_from_file(path: str) -> list[int]:
    with open(path) as f:
        return [
            int(line.strip()) for line in f if line.strip() and not line.strip().startswith("#")
        ]


def _apply_threshold_overrides(
    baseline_cfg: PipelineConfig,
    overrides: dict[str, Any],
) -> PipelineConfig:
    """Return a new PipelineConfig with threshold overrides applied."""
    cfg_dict = baseline_cfg.model_dump(mode="json")
    threshold_overrides = overrides.get("detector_config", {}).get("thresholds", {})

    if threshold_overrides:
        detector_cfg = cfg_dict.setdefault("detector_config", {})
        thresholds = detector_cfg.setdefault("thresholds", {})
        for signal_type, values in threshold_overrides.items():
            thresholds.setdefault(signal_type, {}).update(values)

    return PipelineConfig.model_validate(cfg_dict)


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def _summarize(run: dict[str, Any], label: str) -> dict[str, Any]:
    cards = run.get("cards", [])
    signals = run.get("signals", [])
    enriched = run.get("enriched", [])

    store_ids = [c.get("store_id") for c in cards if c.get("store_id") is not None]
    alert_types = [c.get("alert_type") or c.get("signal_type") for c in cards]
    departments = [c.get("department") for c in cards if c.get("department")]

    return {
        "label": label,
        "analysis_date": run.get("analysis_date"),
        "windows": run.get("windows"),
        "counts": {
            "signals": len(signals),
            "enriched": len(enriched),
            "cards": len(cards),
            "stores": len(set(store_ids)),
        },
        "alert_types": dict(Counter(t for t in alert_types if t)),
        "departments": dict(Counter(d for d in departments if d)),
        "top_stores": dict(Counter(store_ids).most_common(10)),
        "timings": run.get("timings", {}),
        "error": run.get("error"),
    }


def _diff(baseline: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    """Compare two summaries and return a delta report."""
    return {
        "signals_delta": proposed["counts"]["signals"] - baseline["counts"]["signals"],
        "enriched_delta": proposed["counts"]["enriched"] - baseline["counts"]["enriched"],
        "cards_delta": proposed["counts"]["cards"] - baseline["counts"]["cards"],
        "stores_delta": proposed["counts"]["stores"] - baseline["counts"]["stores"],
        "alert_type_changes": {
            atype: proposed["alert_types"].get(atype, 0) - baseline["alert_types"].get(atype, 0)
            for atype in set(baseline["alert_types"]) | set(proposed["alert_types"])
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest pipeline threshold changes on a subset of stores.",
    )
    parser.add_argument("--client", required=True, help="Client config name")
    parser.add_argument("--analysis-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--store-ids",
        help="Comma-separated store IDs (e.g. 508,492,641).",
    )
    parser.add_argument(
        "--store-ids-file",
        help="Path to a file with one store ID per line.",
    )
    parser.add_argument(
        "--signal-types",
        help="Comma-separated signal types to run (e.g. OSA,WASTE).",
    )
    parser.add_argument(
        "--proposed-config",
        help="YAML file with partial detector_config.thresholds overrides.",
    )
    parser.add_argument(
        "--variant",
        choices=["baseline", "proposed", "both"],
        default="both",
        help="Which variant(s) to run.",
    )
    parser.add_argument(
        "--output",
        default="backtest_report.json",
        help="JSON file to write the report.",
    )
    parser.add_argument(
        "--max-investigations",
        type=int,
        default=10,
        help="Cap investigation stage to top-N signals by score.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    _load_env()

    store_ids = None
    if args.store_ids_file:
        store_ids = _load_store_ids_from_file(args.store_ids_file)
    elif args.store_ids:
        store_ids = _parse_store_ids(args.store_ids)

    signal_types = None
    if args.signal_types:
        signal_types = [s.strip() for s in args.signal_types.split(",") if s.strip()]

    baseline_cfg = load_config(args.client)
    proposed_cfg = baseline_cfg
    if args.proposed_config:
        proposed_cfg = _apply_threshold_overrides(baseline_cfg, _load_yaml(args.proposed_config))

    session = _create_session()

    results: dict[str, Any] = {
        "client": args.client,
        "analysis_date": args.analysis_date,
        "store_ids": store_ids,
        "signal_types": signal_types,
    }

    if args.variant in ("baseline", "both"):
        print(f"[backtest] Running baseline for {args.client} on {args.analysis_date}...")
        baseline_run = run_experiment(
            cfg=baseline_cfg,
            analysis_date=args.analysis_date,
            store_ids=store_ids,
            signal_types=signal_types,
            max_investigations=args.max_investigations,
            session=session,
        )
        results["baseline"] = _summarize(baseline_run, "baseline")

    if args.variant in ("proposed", "both"):
        if proposed_cfg is baseline_cfg and args.variant == "proposed":
            raise ValueError("--proposed-config is required when --variant=proposed")
        print(f"[backtest] Running proposed for {args.client} on {args.analysis_date}...")
        proposed_run = run_experiment(
            cfg=proposed_cfg,
            analysis_date=args.analysis_date,
            store_ids=store_ids,
            signal_types=signal_types,
            max_investigations=args.max_investigations,
            session=session,
        )
        results["proposed"] = _summarize(proposed_run, "proposed")

    if args.variant == "both" and "baseline" in results and "proposed" in results:
        results["diff"] = _diff(results["baseline"], results["proposed"])

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"[backtest] Report written to {args.output}")

    if "diff" in results:
        d = results["diff"]
        print(
            f"[backtest] Delta: signals {d['signals_delta']:+d}, "
            f"enriched {d['enriched_delta']:+d}, cards {d['cards_delta']:+d}, "
            f"stores {d['stores_delta']:+d}"
        )


if __name__ == "__main__":
    main()
