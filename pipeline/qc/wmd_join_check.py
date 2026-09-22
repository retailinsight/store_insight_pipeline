"""Diagnostic check for WMD hierarchy join compatibility.

Reads the EoE hierarchy adapters and contracts, then answers:

1. Does each adapter output match its contract?
2. Can the WMD item key (UPC) join to the OSA item key (ITEM_CODE)?
3. Can EAN be used to bridge the WMD and OSA item hierarchies?

Typical usage:

    python -m store_insight.pipeline.qc.wmd_join_check

Or from Python:

    from store_insight.pipeline.qc.wmd_join_check import check_wmd_joins, report
    print(report(check_wmd_joins()))
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from store_insight.pipeline.contracts import load_contract

_WMD_CONTRACT_NAME = "wmd_item_hierarchy"
_WMD_ADAPTER_FILE = Path(__file__).parents[1] / "adapters" / "eastofengland" / "wmd_hierarchy.sql"
_OSA_CONTRACT_NAME = "hierarchy"
_OSA_ADAPTER_FILE = Path(__file__).parents[1] / "adapters" / "eastofengland" / "hierarchy.sql"


def _parse_adapter_aliases(sql: str) -> dict[str, str]:
    """Return a mapping of output column -> source expression from a SELECT."""
    aliases: dict[str, str] = {}
    # Find the SELECT body (everything between SELECT and FROM).
    match = re.search(r"SELECT\s+(?:DISTINCT\s+)?(.*?)\s+FROM\s", sql, re.DOTALL | re.IGNORECASE)
    if not match:
        return aliases

    body = match.group(1)
    # Split on commas that are not inside parentheses.
    raw_columns = re.split(r",\s*(?![^()]*\))", body)

    for raw in raw_columns:
        raw = raw.strip()
        if not raw:
            continue
        # Remove inline comments.
        raw = re.sub(r"--.*", "", raw).strip()
        # Split on AS (last occurrence).
        if re.search(r"\bAS\b", raw, re.IGNORECASE):
            source, alias = re.split(r"\bAS\b", raw, flags=re.IGNORECASE, maxsplit=1)
            aliases[alias.strip().strip('"')] = source.strip()
        else:
            aliases[raw.strip().strip('"')] = raw.strip()

    return aliases


def check_wmd_joins() -> dict[str, Any]:
    """Run the WMD hierarchy adapter/contract compatibility check."""
    wmd_contract = load_contract(_WMD_CONTRACT_NAME)
    wmd_sql = _WMD_ADAPTER_FILE.read_text(encoding="utf-8")
    wmd_aliases = _parse_adapter_aliases(wmd_sql)

    osa_contract = load_contract(_OSA_CONTRACT_NAME)
    osa_sql = _OSA_ADAPTER_FILE.read_text(encoding="utf-8")
    osa_aliases = _parse_adapter_aliases(osa_sql)

    wmd_contract_columns = set(wmd_contract.get("columns", {}).keys())
    wmd_adapter_columns = set(wmd_aliases.keys())
    osa_contract_columns = set(osa_contract.get("columns", {}).keys())
    osa_adapter_columns = set(osa_aliases.keys())

    # The adapter column intended to bridge WMD and OSA items.
    bridge_source = wmd_aliases.get("OSA_ITEM_CODE", "")
    bridge_can_join_osa = "ITEM_ID" in bridge_source.upper()

    # EAN bridge check: does both sides expose EAN from a source column?
    wmd_has_ean = "EAN" in wmd_aliases
    osa_has_ean = "EAN" in osa_aliases
    both_expose_ean = wmd_has_ean and osa_has_ean

    return {
        "wmd_contract": wmd_contract,
        "wmd_adapter_file": str(_WMD_ADAPTER_FILE),
        "wmd_adapter_aliases": wmd_aliases,
        "wmd_contract_columns": wmd_contract_columns,
        "wmd_adapter_columns": wmd_adapter_columns,
        "wmd_missing_in_adapter": sorted(wmd_contract_columns - wmd_adapter_columns),
        "wmd_extra_in_adapter": sorted(wmd_adapter_columns - wmd_contract_columns),
        "osa_contract": osa_contract,
        "osa_adapter_file": str(_OSA_ADAPTER_FILE),
        "osa_adapter_aliases": osa_aliases,
        "osa_contract_columns": osa_contract_columns,
        "osa_adapter_columns": osa_adapter_columns,
        "osa_missing_in_adapter": sorted(osa_contract_columns - osa_adapter_columns),
        "osa_extra_in_adapter": sorted(osa_adapter_columns - osa_contract_columns),
        "upc_source": wmd_aliases.get("UPC", ""),
        "osa_item_code_source": bridge_source,
        "upc_joins_to_osa_item_code": bridge_can_join_osa,
        "wmd_has_ean": wmd_has_ean,
        "osa_has_ean": osa_has_ean,
        "both_expose_ean": both_expose_ean,
    }


def _render_alignment(
    label: str,
    contract_columns: set[str],
    adapter_columns: set[str],
) -> list[str]:
    lines = [f"### {label}", ""]
    lines.append(f"- Contract columns: `{sorted(contract_columns)}`")
    lines.append(f"- Adapter columns: `{sorted(adapter_columns)}`")
    missing = sorted(contract_columns - adapter_columns)
    extra = sorted(adapter_columns - contract_columns)
    if missing:
        lines.append(f"- **Missing in adapter:** `{missing}`")
    if extra:
        lines.append(f"- **Extra in adapter:** `{extra}`")
    if not missing and not extra:
        lines.append("- All contract columns are produced by the adapter.")
    return lines


def report(results: dict[str, Any]) -> str:
    """Render the diagnostic as Markdown."""
    lines: list[str] = [
        "# WMD Hierarchy Join Compatibility Check",
        "",
        f"WMD adapter: `{results['wmd_adapter_file']}`",
        f"OSA adapter: `{results['osa_adapter_file']}`",
        "",
        "## Adapter aliases",
        "",
        "### WMD hierarchy",
        "",
    ]
    for output_col, source_expr in sorted(results["wmd_adapter_aliases"].items()):
        lines.append(f"- `{output_col}` ← `{source_expr}`")

    lines.extend(["", "### OSA hierarchy", ""])
    for output_col, source_expr in sorted(results["osa_adapter_aliases"].items()):
        lines.append(f"- `{output_col}` ← `{source_expr}`")

    lines.extend(
        [
            "",
            "## Contract vs adapter column alignment",
            "",
        ]
    )
    lines.extend(
        _render_alignment(
            "WMD hierarchy",
            results["wmd_contract_columns"],
            results["wmd_adapter_columns"],
        )
    )
    lines.append("")
    lines.extend(
        _render_alignment(
            "OSA hierarchy",
            results["osa_contract_columns"],
            results["osa_adapter_columns"],
        )
    )

    lines.extend(
        [
            "",
            "## Join-key analysis",
            "",
            f"- `UPC` source expression: `{results['upc_source']}`",
            f"- `OSA_ITEM_CODE` source expression: `{results['osa_item_code_source']}`",
            "",
            "### Can WMD `UPC` join to OSA `ITEM_CODE`?",
            "",
        ]
    )

    if results["upc_joins_to_osa_item_code"]:
        lines.append(
            "**Yes** — the adapter aliases the same source column to both `UPC` and "
            "`OSA_ITEM_CODE`, so the keys are the same underlying value."
        )
    else:
        lines.append(
            "**No** — `UPC` is sourced from `ITEM_ID` (the WMD item key), while "
            "`OSA_ITEM_CODE` is sourced from a different column. They are not the "
            "same identifier and cannot be joined directly."
        )

    lines.extend(
        [
            "",
            "### What does join correctly?",
            "",
            "- `wmd_hierarchy.UPC` joins to `markdown_log.UPC`, `markdown_sales.UPC`, "
            "and `wastage.UPC` — all three WMD transactional contracts use UPC.",
            "- `wmd_hierarchy.OSA_ITEM_CODE` is the only column that *could* bridge to "
            "`osa.ITEM_CODE` / `hierarchy.ITEM_CODE`, but only if its source expression "
            "is the same item identifier.",
        ]
    )

    lines.extend(
        [
            "",
            "## EAN bridge analysis",
            "",
            f"- WMD hierarchy exposes `EAN`: **{results['wmd_has_ean']}**",
            f"- OSA hierarchy exposes `EAN`: **{results['osa_has_ean']}**",
            "",
        ]
    )

    if results["both_expose_ean"]:
        lines.append(
            "**Yes — EAN can be used as a bridge.** Both hierarchies surface `EAN`, so "
            "`hierarchy.EAN` can be joined to `wmd_hierarchy.EAN`. From there you can "
            "map `hierarchy.ITEM_CODE` ↔ `wmd_hierarchy.UPC`."
        )
        lines.extend(
            [
                "",
                "### Suggested Snowflake probe",
                "",
                "Check how complete the EAN bridge is between the two hierarchies:",
                "",
                "```sql",
                "SELECT",
                "    COUNT(DISTINCT h.ITEM_ID) AS osa_items_with_ean,",
                "    COUNT(DISTINCT w.ITEM_ID) AS wmd_items_with_ean,",
                "    COUNT(DISTINCT h.ITEM_ID) - COUNT(DISTINCT w.ITEM_ID) AS only_in_osa,",
                "    COUNT(DISTINCT w.ITEM_ID) - COUNT(DISTINCT h.ITEM_ID) AS only_in_wmd",
                "FROM (SELECT DISTINCT ITEM_ID, EAN FROM ANALYSIS.FINAL.LSM_ITEM_HIERARCHY) h",
                "FULL OUTER JOIN (SELECT DISTINCT ITEM_ID, EAN FROM ANALYSIS.FINAL.WMD_ITEM_HIERARCHY) w",
                "    ON h.EAN = w.EAN;",
                "```",
                "",
                "If `only_in_osa` and `only_in_wmd` are small, EAN is a reliable bridge.",
            ]
        )
    else:
        lines.append(
            "**No — EAN cannot be used as a bridge yet.** At least one hierarchy does "
            "not surface `EAN` in its adapter."
        )

    if not results["upc_joins_to_osa_item_code"]:
        lines.extend(
            [
                "",
                "## Suggested Snowflake probe (non-EAN bridge)",
                "",
                "Run this against the raw EoE source to see how many WMD items have an "
                "OSA item-code bridge via `HIERARCHY_LEVEL_1_ID`:",
                "",
                "```sql",
                "SELECT",
                "    COUNT(DISTINCT ITEM_ID) AS wmd_items,",
                "    COUNT(DISTINCT HIERARCHY_LEVEL_1_ID) AS osa_item_code_values,",
                "    COUNT(DISTINCT ITEM_ID) - COUNT(DISTINCT HIERARCHY_LEVEL_1_ID) AS diff",
                "FROM ANALYSIS.FINAL.WMD_ITEM_HIERARCHY;",
                "```",
                "",
                "If `diff` is large (or `osa_item_code_values` is tiny), the bridge column "
                "is not a real item-level join key.",
            ]
        )

    return "\n".join(lines)


def main() -> None:
    """Run the diagnostic, print the report, and write it to the contracts folder."""
    results = check_wmd_joins()
    rendered = report(results)
    report_path = Path(__file__).parents[1] / "contracts" / "wmd_join_check_report.md"
    report_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote report to {report_path}\n")
    print(rendered)


if __name__ == "__main__":
    main()
