"""Join overlap probe for Store Insight contracts.

For every declared join in every contract, this script queries Snowflake to
measure how well the keys on each side actually overlap. It reports:

- distinct key combinations on the left
- distinct key combinations on the right
- how many left keys have at least one right match
- how many right keys have at least one left match

Usage:
    python -m store_insight.pipeline.qc.join_overlap_check --client eastofengland
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Path setup mirror of other pipeline/tools scripts.
_HERE = Path(__file__).resolve().parent
_PIPELINE = _HERE.parent
_SI_PKG = _PIPELINE.parent
_REPO_ROOT = _SI_PKG.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from store_insight.pipeline.config.loader import load_config  # noqa: E402
from store_insight.pipeline.contracts import list_contracts, load_contract  # noqa: E402
from store_insight.pipeline.pipeline.session import create_session  # noqa: E402


def _quote(col: str) -> str:
    """Return a safely quoted identifier for Snowflake SQL."""
    return f'"{col}"'


def _build_overlap_sql(left_view: str, right_view: str, match: dict[str, str]) -> str:
    """Build a three-way probe SQL for a single join."""
    left_cols = ", ".join(_quote(c) for c in match.keys())
    right_cols = ", ".join(_quote(c) for c in match.values())
    join_condition = " AND ".join(
        f"l.{_quote(lc)} = r.{_quote(rc)}"
        for lc, rc in match.items()
    )

    return f"""
WITH left_keys AS (
    SELECT DISTINCT {left_cols}
    FROM {left_view}
),
right_keys AS (
    SELECT DISTINCT {right_cols}
    FROM {right_view}
),
left_matched AS (
    SELECT DISTINCT {', '.join(f'l.{_quote(c)}' for c in match.keys())}
    FROM left_keys l
    JOIN right_keys r ON {join_condition}
),
right_matched AS (
    SELECT DISTINCT {', '.join(f'r.{_quote(c)}' for c in match.values())}
    FROM right_keys r
    JOIN left_keys l ON {join_condition}
)
SELECT
    (SELECT COUNT(*) FROM left_keys) AS LEFT_KEYS,
    (SELECT COUNT(*) FROM right_keys) AS RIGHT_KEYS,
    (SELECT COUNT(*) FROM left_matched) AS MATCHED_LEFT,
    (SELECT COUNT(*) FROM right_matched) AS MATCHED_RIGHT
"""


def check_join_overlaps(client: str) -> dict[str, Any]:
    """Run overlap probes for every declared join for ``client``."""
    cfg = load_config(client)
    session = create_session(cfg)

    # Config table keys do not always match contract names.
    _CONTRACT_TO_TABLE_KEY = {
        "wmd_item_hierarchy": "wmd_hierarchy",
        "wmd_store_hierarchy": "store_hierarchy",
    }

    tables = cfg.tables.model_dump()
    results: list[dict[str, Any]] = []

    for contract_name in list_contracts():
        contract = load_contract(contract_name)
        joins = contract.get("joins", [])
        if not joins:
            continue

        left_key = _CONTRACT_TO_TABLE_KEY.get(contract_name, contract_name)
        left_view = tables.get(left_key)
        if not left_view:
            results.append(
                {
                    "left_contract": contract_name,
                    "right_contract": None,
                    "status": "skipped",
                    "reason": f"no view configured in cfg.tables for '{contract_name}' (looked up key '{left_key}')",
                }
            )
            continue

        for join in joins:
            right_contract = join["contract"]
            right_key = _CONTRACT_TO_TABLE_KEY.get(right_contract, right_contract)
            right_view = tables.get(right_key)
            if not right_view:
                results.append(
                    {
                        "left_contract": contract_name,
                        "right_contract": right_contract,
                        "status": "skipped",
                        "reason": f"no view configured in cfg.tables for '{right_contract}' (looked up key '{right_key}')",
                    }
                )
                continue

            sql = _build_overlap_sql(left_view, right_view, join["match"])
            try:
                df = session.sql(sql).collect()
                row = df[0]
                left_keys = row["LEFT_KEYS"]
                right_keys = row["RIGHT_KEYS"]
                matched_left = row["MATCHED_LEFT"]
                matched_right = row["MATCHED_RIGHT"]

                results.append(
                    {
                        "left_contract": contract_name,
                        "right_contract": right_contract,
                        "left_view": left_view,
                        "right_view": right_view,
                        "match": join["match"],
                        "status": "ok",
                        "left_keys": left_keys,
                        "right_keys": right_keys,
                        "matched_left": matched_left,
                        "matched_right": matched_right,
                        "left_coverage": matched_left / left_keys if left_keys else 0.0,
                        "right_coverage": matched_right / right_keys if right_keys else 0.0,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "left_contract": contract_name,
                        "right_contract": right_contract,
                        "left_view": left_view,
                        "right_view": right_view,
                        "match": join["match"],
                        "status": "error",
                        "reason": str(exc),
                    }
                )

    return {"client": client, "results": results}


def _fmt_coverage(num: int, denom: int) -> str:
    if not denom:
        return "n/a"
    pct = 100.0 * num / denom
    return f"{num:,} / {denom:,} ({pct:.1f}%)"


def report(data: dict[str, Any]) -> str:
    """Render overlap results as Markdown."""
    lines = [
        "# Join Overlap Probe",
        "",
        f"Client: `{data['client']}`",
        "",
        "This report counts distinct key combinations on each side of every "
        "declared contract join, then counts how many of those keys have at "
        "least one match on the opposite side. Low coverage is a red flag for "
        "silent join failures.",
        "",
    ]

    for r in data["results"]:
        if r["status"] == "skipped":
            lines.append(
                f"## {r['left_contract']} → {r.get('right_contract', '?')}\n\n"
                f"**Skipped:** {r['reason']}"
            )
            continue

        if r["status"] == "error":
            lines.append(
                f"## {r['left_contract']} → {r['right_contract']}\n\n"
                f"**Error:** `{r['reason']}`"
            )
            continue

        match_str = ", ".join(f"{lc} = {rc}" for lc, rc in r["match"].items())
        lines.extend(
            [
                f"## {r['left_contract']} → {r['right_contract']}",
                "",
                f"- Left view: `{r['left_view']}`",
                f"- Right view: `{r['right_view']}`",
                f"- Join keys: `{match_str}`",
                "",
                "| Side | Distinct keys | Matched | Coverage |",
                "|---|---|---|---|",
                f"| Left ({r['left_contract']}) | {r['left_keys']:,} | {_fmt_coverage(r['matched_left'], r['left_keys'])} |",
                f"| Right ({r['right_contract']}) | {r['right_keys']:,} | {_fmt_coverage(r['matched_right'], r['right_keys'])} |",
                "",
            ]
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe declared contract joins for key overlap.")
    parser.add_argument("--client", required=True, help="Client config name")
    args = parser.parse_args()

    data = check_join_overlaps(args.client)
    rendered = report(data)
    report_path = Path(__file__).parents[1] / "contracts" / "join_overlap_report.md"
    report_path.write_text(rendered, encoding="utf-8")
    print(rendered)
    print(f"\nWrote report to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
