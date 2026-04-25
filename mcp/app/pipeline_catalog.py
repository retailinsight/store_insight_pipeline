"""
Pipeline catalog accessors for the MCP server.

Loads ``pipeline_catalog.json`` (regenerated at dev time by
``store_insight/pipeline/tools/build_catalog.py``) and exposes typed lookup
functions for the MCP tools defined in ``server.py``.

The JSON file is the single source of truth for "what does the alerts pipeline
contain" — detectors, gatherers, signal types, investigation skills, and
threshold defaults.  See the build script for how it's assembled from the
live pipeline package.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).parent / "pipeline_catalog.json"


@lru_cache(maxsize=1)
def _catalog() -> dict:
    """Load and cache the catalog JSON. Cached for the life of the process."""
    if not _CATALOG_PATH.is_file():
        raise FileNotFoundError(
            f"pipeline_catalog.json not found at {_CATALOG_PATH}. "
            "Run `python store_insight/pipeline/tools/build_catalog.py` to "
            "regenerate it."
        )
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def overview() -> dict:
    """Top-level catalog metadata: pipeline summary, stages, generated_at."""
    cat = _catalog()
    return {
        "generated_at":     cat["generated_at"],
        "pipeline_summary": cat["pipeline_summary"],
        "stages":           cat["stages"],
        "signal_types":     sorted(cat["signal_types"].keys()),
    }


def list_signal_types() -> dict:
    """One row per signal type with merge_key, factory, bucket, and field count."""
    cat = _catalog()
    rows = []
    for stype, entry in cat["signal_types"].items():
        rows.append({
            "signal_type": stype,
            "bucket":      entry.get("bucket"),
            "description": entry.get("description"),
            "merge_key":   entry.get("merge_key"),
            "factory":     entry.get("factory"),
            "field_count": len(entry.get("fields", [])),
            "detector_count": len(entry.get("detectors", [])),
            "gatherer_count": len(entry.get("gatherers", [])),
            "investigator_engine": entry.get("investigator", {}).get("engine"),
        })
    rows.sort(key=lambda r: r["signal_type"])
    return {"signal_types": rows}


def get_signal_type(signal_type: str) -> dict:
    """Full record for a single signal type, including fields."""
    cat = _catalog()
    key = signal_type.upper()
    entry = cat["signal_types"].get(key)
    if entry is None:
        raise ValueError(
            f"Unknown signal_type {signal_type!r}. "
            f"Known: {sorted(cat['signal_types'].keys())}"
        )
    return {
        "signal_type": key,
        **entry,
    }


def list_detectors(signal_type: str | None = None) -> dict:
    """All detectors, optionally filtered to one signal type."""
    cat = _catalog()
    if signal_type:
        key = signal_type.upper()
        if key not in cat["signal_types"]:
            raise ValueError(
                f"Unknown signal_type {signal_type!r}. "
                f"Known: {sorted(cat['signal_types'].keys())}"
            )
        items = [
            {**d, "signal_type": key}
            for d in cat["signal_types"][key]["detectors"]
        ]
    else:
        items = []
        for stype, entry in cat["signal_types"].items():
            for d in entry["detectors"]:
                items.append({**d, "signal_type": stype})
    items.sort(key=lambda d: (d["signal_type"], d["name"]))
    return {"detectors": items, "count": len(items)}


def list_gatherers(signal_type: str | None = None) -> dict:
    """All gatherer dispatches, optionally filtered to one signal type."""
    cat = _catalog()
    if signal_type:
        key = signal_type.upper()
        if key not in cat["signal_types"]:
            raise ValueError(
                f"Unknown signal_type {signal_type!r}. "
                f"Known: {sorted(cat['signal_types'].keys())}"
            )
        items = [
            {**g, "signal_type": key}
            for g in cat["signal_types"][key]["gatherers"]
        ]
    else:
        items = []
        for stype, entry in cat["signal_types"].items():
            for g in entry["gatherers"]:
                items.append({**g, "signal_type": stype})
    items.sort(key=lambda g: (g["signal_type"], g["name"]))
    return {"gatherers": items, "count": len(items)}


def list_thresholds(detector: str | None = None) -> dict:
    """
    All ``DetectorConfig`` threshold fields with defaults and which detectors
    consume each.

    Args:
        detector: Optional case-insensitive substring filter on the
            ``"<SIGNAL_TYPE> <DETECTOR_NAME>"`` label, e.g. ``"OSA"`` returns
            only thresholds used by OSA detectors; ``"WASTE WOW"`` narrows to
            the waste WoW detector.
    """
    cat = _catalog()
    rows = list(cat["thresholds"])
    if detector:
        needle = detector.upper()
        rows = [
            r for r in rows
            if any(needle in d.upper() for d in r.get("detectors", []))
        ]
    return {"thresholds": rows, "count": len(rows)}


def get_investigation_skill(signal_type: str) -> dict:
    """Return the investigator engine + raw skill markdown for a signal type."""
    cat = _catalog()
    key = signal_type.upper()
    entry = cat["signal_types"].get(key)
    if entry is None:
        raise ValueError(
            f"Unknown signal_type {signal_type!r}. "
            f"Known: {sorted(cat['signal_types'].keys())}"
        )
    inv = entry.get("investigator", {})
    return {
        "signal_type": key,
        "engine":      inv.get("engine"),
        "skill_file":  inv.get("skill_file"),
        "description": inv.get("description"),
        "skill_text":  inv.get("skill_text", ""),
    }


# ---------------------------------------------------------------------------
# Reference resource — one consolidated markdown view for LLM consumption
# ---------------------------------------------------------------------------

def _render_reference_markdown() -> str:
    """Assemble a single Markdown document covering the whole pipeline catalog."""
    cat = _catalog()
    lines: list[str] = []
    lines.append("# Alerts Pipeline — Live Reference")
    lines.append("")
    lines.append(f"_Generated: {cat['generated_at']}_")
    lines.append("")
    lines.append(cat["pipeline_summary"])
    lines.append("")
    lines.append("## Stages")
    for k, v in cat["stages"].items():
        lines.append(f"- **{k}** — {v}")
    lines.append("")

    for stype, entry in sorted(cat["signal_types"].items()):
        lines.append(f"## Signal type: `{stype}` _({entry.get('bucket', '')})_")
        lines.append("")
        lines.append(entry.get("description", ""))
        lines.append("")
        lines.append(f"- **Merge key**: `{entry.get('merge_key')}`")
        lines.append(f"- **Factory**: `{entry.get('factory')}`")
        inv = entry.get("investigator", {})
        lines.append(
            f"- **Investigator**: `{inv.get('engine', '')}` "
            f"(skill: `{inv.get('skill_file', '')}`)"
        )
        lines.append("")

        # Detectors
        lines.append("### Detectors")
        if not entry.get("detectors"):
            lines.append("_(none)_")
        for d in entry.get("detectors", []):
            lines.append(f"- **{d['name']}** (`{d['module']}`)")
            lines.append(f"  - Problem: {d['problem']}")
            lines.append(f"  - Action: {d['action']}")
            lines.append(f"  - Baseline: {d['baseline']}")
            lines.append(f"  - Logic: {d['logic']}")
            if d.get("config_keys"):
                lines.append(
                    "  - Thresholds: "
                    + ", ".join(f"`{k}`" for k in d["config_keys"])
                )
        lines.append("")

        # Gatherers
        lines.append("### Gatherers (Stage 2 facts)")
        if not entry.get("gatherers"):
            lines.append("_(none)_")
        for g in entry.get("gatherers", []):
            keys = ", ".join(f"`{k}`" for k in g.get("facts_keys", []))
            lines.append(f"- **{g['name']}** — {g.get('description', '')}")
            if keys:
                lines.append(f"  - Facts produced: {keys}")
        lines.append("")

        # Signal fields
        lines.append("### Signal fields")
        for f in entry.get("fields", []):
            lines.append(f"- `{f['name']}`: `{f['type']}`")
        lines.append("")

    # Thresholds
    lines.append("## Thresholds (`DetectorConfig`)")
    lines.append("")
    lines.append("| Field | Type | Default | Used by |")
    lines.append("|---|---|---|---|")
    for t in cat["thresholds"]:
        users = ", ".join(t.get("detectors", [])) or "_(unused)_"
        lines.append(
            f"| `{t['name']}` | `{t['type']}` | `{t['default']!r}` | {users} |"
        )
    lines.append("")

    return "\n".join(lines)


@lru_cache(maxsize=1)
def reference_markdown() -> str:
    """Cached consolidated Markdown reference document."""
    return _render_reference_markdown()
