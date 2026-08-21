"""Contract data-quality checker.

Reads every YAML contract in ``pipeline/contracts`` and reports:

* whether declared joins point to existing contracts/columns
* whether join keys have compatible types
* whether grain columns exist
* whether ``data_quality_findings`` reference real columns
* implicit joins (same column name appearing in multiple contracts) and any
  type mismatches between them
* specific item-identifier confusion (ITEM_ID / UPC / ITEM_CODE)

Typical usage:

    python -m store_insight.pipeline.qc.contract_quality

Or from Python:

    from store_insight.pipeline.qc.contract_quality import check_contracts, report
    results = check_contracts()
    print(report(results))
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from store_insight.pipeline.contracts import all_contracts


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _severity_sort_key(issue: dict[str, Any]) -> tuple[int, str]:
    return (_SEVERITY_ORDER.get(issue.get("severity", "info"), 99), issue.get("contract", ""))


def check_contracts() -> dict[str, Any]:
    """Load every contract and run consistency checks."""
    contracts = all_contracts()

    columns_by_contract: dict[str, dict[str, dict[str, Any]]] = {}
    for name, contract in contracts.items():
        columns_by_contract[name] = {
            col_name: col_def for col_name, col_def in contract.get("columns", {}).items()
        }

    issues: list[dict[str, Any]] = []

    # Declared joins: target exists, columns exist, types match.
    for name, contract in contracts.items():
        for idx, join in enumerate(contract.get("joins", []), start=1):
            target = join.get("contract")
            if target not in contracts:
                issues.append(
                    {
                        "contract": name,
                        "check": "join_target_exists",
                        "severity": "critical",
                        "message": f"Join #{idx} references unknown contract '{target}'.",
                        "context": join,
                    }
                )
                continue

            target_cols = columns_by_contract[target]
            for left_col, right_col in join.get("match", {}).items():
                if left_col not in columns_by_contract[name]:
                    issues.append(
                        {
                            "contract": name,
                            "check": "join_source_column_exists",
                            "severity": "critical",
                            "message": (
                                f"Join #{idx} to '{target}' uses source column "
                                f"'{left_col}', which is not defined in '{name}'."
                            ),
                            "context": join,
                        }
                    )
                    continue

                if right_col not in target_cols:
                    issues.append(
                        {
                            "contract": name,
                            "check": "join_target_column_exists",
                            "severity": "critical",
                            "message": (
                                f"Join #{idx} to '{target}' references target column "
                                f"'{right_col}', which is not defined in '{target}'."
                            ),
                            "context": join,
                        }
                    )
                    continue

                left_type = columns_by_contract[name][left_col].get("type")
                right_type = target_cols[right_col].get("type")
                if left_type and right_type and left_type != right_type:
                    issues.append(
                        {
                            "contract": name,
                            "check": "join_type_compatibility",
                            "severity": "high",
                            "message": (
                                f"Join '{name}.{left_col} -> {target}.{right_col}' "
                                f"mixes types {left_type} and {right_type}."
                            ),
                            "context": {
                                "join": join,
                                "left_type": left_type,
                                "right_type": right_type,
                            },
                        }
                    )

    # Grain columns exist.
    for name, contract in contracts.items():
        for grain_col in contract.get("grain", []):
            if grain_col not in columns_by_contract[name]:
                issues.append(
                    {
                        "contract": name,
                        "check": "grain_column_exists",
                        "severity": "critical",
                        "message": f"Grain column '{grain_col}' is not defined in columns.",
                    }
                )

    # data_quality_findings reference real columns.
    for name, contract in contracts.items():
        for finding in contract.get("data_quality_findings", []):
            col = finding.get("column")
            if col and col not in columns_by_contract[name]:
                issues.append(
                    {
                        "contract": name,
                        "check": "finding_column_exists",
                        "severity": "medium",
                        "message": (
                            f"data_quality_findings references column '{col}', "
                            "which is not defined in this contract."
                        ),
                        "context": finding,
                    }
                )

    # Implicit joins: same column name in multiple contracts.
    occurrences: dict[str, list[str]] = defaultdict(list)
    for name, cols in columns_by_contract.items():
        for col_name in cols:
            occurrences[col_name].append(name)

    implicit_joins: list[dict[str, Any]] = []
    for col_name, contract_names in occurrences.items():
        if len(contract_names) > 1:
            types = {
                columns_by_contract[c][col_name].get("type")
                for c in contract_names
                if columns_by_contract[c][col_name].get("type")
            }
            implicit_joins.append(
                {
                    "column": col_name,
                    "contracts": sorted(contract_names),
                    "types": sorted(types),
                    "type_mismatch": len(types) > 1,
                }
            )

    # Item-identifier cross-check: where do ITEM_ID, UPC, ITEM_CODE, EAN appear?
    item_idents: dict[str, list[tuple[str, str, bool]]] = defaultdict(list)
    for name, cols in columns_by_contract.items():
        for col_name in cols:
            if col_name in ("ITEM_ID", "UPC", "ITEM_CODE", "EAN"):
                item_idents[col_name].append(
                    (
                        name,
                        cols[col_name].get("type", "unknown"),
                        cols[col_name].get("required", False),
                    )
                )

    issues.sort(key=_severity_sort_key)
    implicit_joins.sort(key=lambda j: (not j["type_mismatch"], j["column"]))

    return {
        "contracts": contracts,
        "columns_by_contract": columns_by_contract,
        "issues": issues,
        "implicit_joins": implicit_joins,
        "item_identifiers": dict(item_idents),
    }


def report(results: dict[str, Any]) -> str:
    """Render checker results as Markdown."""
    contracts = results["contracts"]
    issues = results["issues"]
    implicit_joins = results["implicit_joins"]
    item_idents = results["item_identifiers"]

    lines: list[str] = [
        "# Contract Data-Quality Report",
        "",
        f"Contracts scanned: **{len(contracts)}**",
        f"Issues found: **{len(issues)}**",
        "",
        "## Summary",
        "",
    ]

    if not issues:
        lines.append("No contract-level issues detected.")
    else:
        for severity in ("critical", "high", "medium", "low", "info"):
            count = sum(1 for i in issues if i.get("severity") == severity)
            if count:
                lines.append(f"- **{severity.capitalize()}**: {count}")

    # Item identifier confusion — the user's specific concern.
    lines.extend(
        [
            "",
            "## Item identifier usage",
            "",
            "The pipeline currently mixes four item identifiers across contracts. "
            "This section shows which contract uses which key, its declared type, "
            "and whether it is required.",
            "",
        ]
    )
    for ident in ("ITEM_ID", "UPC", "ITEM_CODE", "EAN"):
        entries = item_idents.get(ident, [])
        if entries:
            lines.append(f"### {ident}")
            lines.append("")
            for contract, typ, required in entries:
                req = "required" if required else "optional"
                lines.append(f"- `{contract}`: type `{typ}`, {req}")
            lines.append("")

    lines.extend(
        [
            "## Issues",
            "",
        ]
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        grouped[issue.get("contract", "general")].append(issue)

    if not issues:
        lines.append("No issues to report.")
    else:
        for contract, contract_issues in sorted(grouped.items()):
            lines.append(f"### {contract}")
            lines.append("")
            for issue in contract_issues:
                sev = issue.get("severity", "info").upper()
                msg = issue.get("message", "")
                lines.append(f"- **[{sev}]** {msg}")
                ctx = issue.get("context")
                if ctx:
                    lines.append(f"  - Context: `{ctx}`")
            lines.append("")

    # Recommendations.
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "1. **Verify the WMD item key.** `wmd_item_hierarchy` now declares both "
            "`ITEM_ID` (source grain) and `UPC` (canonical join key for WMD transactional "
            "tables). The EoE adapter aliases `ITEM_ID` to `UPC`. If other customers "
            "source UPC directly, ensure the grain remains unique per item.",
            "",
            "2. **Maintain `ITEM_CODE` type discipline.** `feedback`, `osa`, and "
            "`hierarchy` now all declare `ITEM_CODE` as `VARCHAR`. The EoE feedback "
            "adapter casts the source `ITEM_ID` to `VARCHAR`. New adapters must keep "
            "this column as `VARCHAR` to preserve the joinability of the compliance "
            "pipeline.",
            "",
            "3. **Treat `ITEM_ID` as two different concepts.** `hierarchy.ITEM_ID` and "
            "`wmd_item_hierarchy.ITEM_ID` share a name but are in different domains. "
            "Consider renaming one (e.g. `WMD_ITEM_ID`) to prevent future confusion.",
            "",
        ]
    )

    # Implicit joins.
    lines.extend(
        [
            "## Implicit joins (shared column names)",
            "",
            "Columns that appear in more than one contract are candidates for implicit "
            "joins. Type mismatches are highlighted.",
            "",
        ]
    )
    for join in implicit_joins:
        mismatch = " **TYPE MISMATCH**" if join["type_mismatch"] else ""
        lines.append(f"### {join['column']}{mismatch}")
        lines.append(f"- Contracts: {', '.join(f'`{c}`' for c in join['contracts'])}")
        lines.append(f"- Types seen: {', '.join(f'`{t}`' for t in join['types']) or '`unknown`'}")
        lines.append("")

    # Per-contract column inventory.
    lines.extend(
        [
            "## Contract column inventory",
            "",
        ]
    )
    for name in sorted(contracts):
        lines.append(f"### {name}")
        lines.append(f"- Grain: {', '.join(f'`{g}`' for g in contracts[name].get('grain', [])) or '`none`'}")
        cols = results["columns_by_contract"][name]
        if cols:
            lines.append("- Columns:")
            for col_name in sorted(cols):
                col = cols[col_name]
                req = "required" if col.get("required") else "optional"
                lines.append(f"  - `{col_name}`: `{col.get('type', 'unknown')}`, {req}")
        else:
            lines.append("- Columns: none")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Run the checker and write a Markdown report into the contracts directory."""
    results = check_contracts()
    report_path = Path(__file__).parents[1] / "contracts" / "data_quality_report.md"
    report_path.write_text(report(results), encoding="utf-8")
    print(f"Wrote report to {report_path}")
    print(f"Issues found: {len(results['issues'])}")
    for severity in ("critical", "high", "medium", "low", "info"):
        count = sum(1 for i in results["issues"] if i.get("severity") == severity)
        if count:
            print(f"  {severity}: {count}")


if __name__ == "__main__":
    main()
