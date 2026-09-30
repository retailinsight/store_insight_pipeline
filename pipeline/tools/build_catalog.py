"""
Build the Pipeline Catalog JSON
================================
Introspects the live ``pipeline.stages`` registries (detectors, gatherers,
signal factories, investigator config, ``DetectorConfig`` thresholds) and
writes a single consolidated JSON document at::

    mcp/app/pipeline_catalog.json

This catalog is the data source for the MCP server's ``list_detectors`` /
``list_gatherers`` / ``list_signal_types`` / ``list_thresholds`` /
``get_investigation_skill`` tools, and for the ``pipeline://reference``
MCP resource.

The MCP service is deployed independently (Railway root = ``mcp/``), so it
cannot import the pipeline package at runtime.  Regenerating this JSON file
at dev time keeps the MCP service self-contained while guaranteeing the
catalog stays in lock-step with the pipeline code.

Run from the repository root (the parent of ``store_insight/``)::

    python store_insight/pipeline/tools/build_catalog.py

Or from anywhere — the script auto-derives the path::

    python <abs-path-to>/build_catalog.py

Re-run any time you add / remove / rename a detector, gatherer, signal type,
threshold field, or skill.  See ``.windsurf/workflows/update-stages.md``.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import typing
from dataclasses import fields
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup — make ``store_insight.pipeline.*`` importable from anywhere.
# ---------------------------------------------------------------------------

_THIS_FILE  = Path(__file__).resolve()
_TOOLS_DIR  = _THIS_FILE.parent                  # pipeline/tools/
_PIPELINE   = _TOOLS_DIR.parent                  # pipeline/
_SI_PKG     = _PIPELINE.parent                   # store_insight/
_REPO_ROOT  = _SI_PKG.parent                     # workspace parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Imports below depend on the path setup above — keep them after it.
from store_insight.pipeline.pipeline.config import DetectorConfig  # noqa: E402
from store_insight.pipeline.stages._1_detect import registry as detect_reg  # noqa: E402
from store_insight.pipeline.stages._1_detect import signals as signals_mod  # noqa: E402
from store_insight.pipeline.stages._3_facts import registry as facts_reg  # noqa: E402

# ---------------------------------------------------------------------------
# Static metadata that is not derivable from the code alone
# ---------------------------------------------------------------------------

# Human-readable description and merge_key shape per signal type. Kept here
# (rather than inside signals.py) so the catalog reads naturally without us
# having to introduce a metadata dataclass for signal types.
SIGNAL_TYPE_META: dict[str, dict[str, str]] = {
    'OSA_STORE_ACTIONABLE': {
        'description': (
            'Store-actionable on-shelf availability has dropped for a '
            'store-department (week-on-week or vs chain).'
        ),
        'merge_key': '(signal_type, store_id, department)',
        'factory':   'make_osa_store_actionable_signal',
        'bucket':    'Availability',
    },
    'OSA_BIG_DROP': {
        'description': (
            'Store-controlled availability dropped sharply from one sales '
            'day to the next for a store-department.'
        ),
        'merge_key': '(signal_type, store_id, department)',
        'factory':   'make_osa_big_drop_signal',
        'bucket':    'Availability',
    },
    'OSA_RECURRING_SLOT': {
        'description': (
            'Recurring OSA lost sales for a store-department in a specific '
            'day-of-week + reporting-period slot.'
        ),
        'merge_key': '(signal_type, store_id, department)',
        'factory':   'make_osa_recurring_slot_signal',
        'bucket':    'Availability',
    },
    'COMPLIANCE': {
        'description': (
            'Store compliance issue — alerts are being dismissed too quickly '
            'without genuine investigation (tick-and-flick).'
        ),
        'merge_key': '(signal_type, store_id)',
        'factory':   'make_compliance_signal',
        'bucket':    'Compliance',
    },
    'MARKDOWN_COMPLIANCE': {
        'description': (
            'Store markdown on-time completion compliance is dropping '
            'week-on-week or sitting below the chain average.'
        ),
        'merge_key': '(signal_type, store_id, department)',
        'factory':   'make_markdown_compliance_signal',
        'bucket':    'Compliance',
    },
    'EXPIRY_DATE_COMPLIANCE': {
        'description': (
            'Store expiry-check completion is dropping over a trailing '
            '7-day window or sitting below the chain average.'
        ),
        'merge_key': '(signal_type, store_id, department)',
        'factory':   'make_expiry_date_compliance_signal',
        'bucket':    'Compliance',
    },
    'PROMPTED_MARKDOWN_COMPLIANCE': {
        'description': (
            'Store prompted-markdown on-time response is dropping '
            'week-on-week or sitting below the chain average.'
        ),
        'merge_key': '(signal_type, store_id, department)',
        'factory':   'make_prompted_markdown_compliance_signal',
        'bucket':    'Compliance',
    },
    'MARKDOWN_OVERRIDE': {
        'description': (
            'Store is overriding the markdown algorithm at an elevated rate '
            'compared to last week or the chain average.'
        ),
        'merge_key': '(signal_type, store_id)',
        'factory':   'make_markdown_override_signal',
        'bucket':    'Markdown',
    },
    'WASTE': {
        'description': (
            'Store straight-to-bin waste rate is rising week-on-week or '
            'sitting above the chain average.'
        ),
        'merge_key': '(signal_type, store_id)',
        'factory':   'make_waste_signal',
        'bucket':    'Waste',
    },
    'WASTE_TRIM': {
        'description': (
            'Store-item markdown dependency alert where markdown sales '
            'exceed the configured ratio of total sales.'
        ),
        'merge_key': '(signal_type, store_id, item_id)',
        'factory':   'make_waste_trim_signal',
        'bucket':    'WASTE_TRIM',
    },
    'MARKDOWN_SELLTHROUGH': {
        'description': (
            'Store markdown sell-through rate is dropping week-on-week or '
            'sitting below the chain average.'
        ),
        'merge_key': '(signal_type, store_id)',
        'factory':   'make_markdown_sellthrough_signal',
        'bucket':    'Markdown',
    },
    'MARKDOWN_SKU': {
        'description': (
            'A specific SKU is being repeatedly marked down, or persistently '
            'overridden, at this store.'
        ),
        'merge_key': '(signal_type, store_id, item_id)',
        'factory':   'make_markdown_sku_signal',
        'bucket':    'Markdown',
    },
    'STRAIGHT_TO_BIN': {
        'description': (
            'Store-department straight-to-bin waste value has exceeded the '
            'configured threshold.'
        ),
        'merge_key': '(signal_type, store_id, department)',
        'factory':   'make_straight_to_bin_signal',
        'bucket':    'Waste',
    },
}

# Map from signal type to the TypedDict class defined in signals.py.
_TYPED_DICT_FOR_SIGNAL: dict[str, type] = {
    'OSA_STORE_ACTIONABLE':         signals_mod.OsaStoreActionableSignal,
    'OSA_BIG_DROP':                 signals_mod.OsaBigDropSignal,
    'OSA_RECURRING_SLOT':           signals_mod.OsaRecurringSlotSignal,
    'COMPLIANCE':                   signals_mod.ComplianceSignal,
    'MARKDOWN_COMPLIANCE':          signals_mod.MarkdownComplianceSignal,
    'EXPIRY_DATE_COMPLIANCE':       signals_mod.ExpiryDateComplianceSignal,
    'PROMPTED_MARKDOWN_COMPLIANCE': signals_mod.PromptedMarkdownComplianceSignal,
    'MARKDOWN_OVERRIDE':            signals_mod.MarkdownOverrideSignal,
    'WASTE':                        signals_mod.WasteSignal,
    'WASTE_TRIM':                   signals_mod.WasteTrimSignal,
    'MARKDOWN_SELLTHROUGH':         signals_mod.MarkdownSellthroughSignal,
    'MARKDOWN_SKU':                 signals_mod.MarkdownSkuSignal,
    'STRAIGHT_TO_BIN':              signals_mod.StraightToBinSignal,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal_type_for_detector_module(mod) -> str:
    """
    Derive the signal type from a detector module's package path.

    e.g. ``store_insight.pipeline.stages._1_detect.detectors.osa.wow``
         → ``'OSA'``
    """
    parts = mod.__name__.split('.')
    # detectors/<alert_type>/<detector_name>
    return parts[-2].upper()


def _annotation_to_str(ann) -> str:
    """Render a typing annotation in a stable, human-readable form."""
    return (
        str(ann)
        .replace('typing.', '')
        .replace("<class '", '')
        .replace("'>", '')
        .replace('NoneType', 'None')
    )


def _signal_fields(signal_type: str) -> list[dict]:
    """Extract field names + types from the TypedDict for a signal type."""
    td = _TYPED_DICT_FOR_SIGNAL[signal_type]
    hints = typing.get_type_hints(td)
    return [
        {'name': name, 'type': _annotation_to_str(ann)}
        for name, ann in hints.items()
    ]


def _read_skill(signal_type: str, skill_file: str) -> str:
    """Load the markdown contents of an investigator skill file."""
    skills_root = _PIPELINE / 'stages' / '_4_investigate'
    path = skills_root / skill_file
    if not path.is_file():
        return ''
    return path.read_text(encoding='utf-8')


# ---------------------------------------------------------------------------
# Catalog assembly
# ---------------------------------------------------------------------------

def _build_detectors_by_signal_type() -> dict[str, list[dict]]:
    """Group every detector's metadata by its signal type."""
    grouped: dict[str, list[dict]] = {}
    for mod in detect_reg.ALL_DETECTORS:
        meta = getattr(mod, 'METADATA', None)
        if meta is None:
            continue
        stype = _signal_type_for_detector_module(mod)
        grouped.setdefault(stype, []).append({
            'name':        meta.name,
            'module':      mod.__name__.rsplit('.', 1)[-1],
            'problem':     meta.problem,
            'action':      meta.action,
            'baseline':    meta.baseline,
            'logic':       meta.logic,
            'config_keys': list(meta.config_keys),
        })
    for items in grouped.values():
        items.sort(key=lambda d: d['name'])
    return grouped


def _build_gatherers_by_signal_type() -> dict[str, list[dict]]:
    """
    For each signal type, list the gatherers that run (in dispatch order),
    annotated with their facts_keys + description from each module's METADATA.
    """
    info_by_name = {info.name: info for info in facts_reg.ALL_GATHERER_INFO}
    grouped: dict[str, list[dict]] = {}
    for stype, modules in facts_reg.SIGNAL_TYPE_GATHERERS.items():
        grouped[stype] = []
        for mod in modules:
            name = mod.__name__.rsplit('.', 1)[-1]
            info = info_by_name.get(name)
            grouped[stype].append({
                'name':         name,
                'facts_keys':   list(info.facts_keys) if info else [],
                'description':  info.description if info else '',
            })
    return grouped


def _build_investigators() -> dict[str, dict]:
    """Load signal_type_investigators.yaml and inline each skill's markdown."""
    yaml_path = (
        _PIPELINE / 'stages' / '_4_investigate' / 'signal_type_investigators.yaml'
    )
    raw = yaml.safe_load(yaml_path.read_text(encoding='utf-8')) or {}
    out: dict[str, dict] = {}
    for stype, entry in raw.items():
        skill_file = entry.get('skill_file', '')
        out[stype] = {
            'engine':      entry.get('engine', ''),
            'skill_file':  skill_file,
            'description': entry.get('description', ''),
            'skill_text':  _read_skill(stype, skill_file),
        }
    return out


def _build_thresholds() -> list[dict]:
    """
    Flatten ``DetectorConfig`` into one row per field, annotated with which
    detectors reference it via ``config_keys``.
    """
    # Invert: config_key -> [(signal_type, detector_name), ...]
    detector_users: dict[str, list[str]] = {}
    for mod in detect_reg.ALL_DETECTORS:
        meta = getattr(mod, 'METADATA', None)
        if meta is None:
            continue
        stype = _signal_type_for_detector_module(mod)
        label = f'{stype} {meta.name}'
        for key in meta.config_keys:
            detector_users.setdefault(key, []).append(label)

    rows: list[dict] = []
    cfg = DetectorConfig()
    for f in fields(DetectorConfig):
        rows.append({
            'name':       f.name,
            'type':       _annotation_to_str(f.type),
            'default':    getattr(cfg, f.name),
            'detectors':  sorted(detector_users.get(f.name, [])),
        })
    return rows


def build_catalog() -> dict:
    """Assemble the full catalog dict."""
    detectors    = _build_detectors_by_signal_type()
    gatherers    = _build_gatherers_by_signal_type()
    investigators = _build_investigators()

    signal_types: dict[str, dict] = {}
    for stype, meta in SIGNAL_TYPE_META.items():
        signal_types[stype] = {
            **meta,
            'fields':       _signal_fields(stype),
            'detectors':    detectors.get(stype, []),
            'gatherers':    gatherers.get(stype, []),
            'investigator': investigators.get(stype, {}),
        }

    return {
        'generated_at':      _dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds'),  # noqa: UP017
        'pipeline_summary':  (
            'Weekly batch that detects retail availability and markdown anomalies, '
            'enriches each signal with supporting facts, generates plain-English '
            'narrative cards, and scores them so the highest-impact issues surface first.'
        ),
        'stages': {
            '1_detect':      'Run lightweight statistical detectors → list of signals.',
            '2_score':       'Score each signal by projected £ cost; filter top-N per store before enrichment.',
            '3_facts':       'Enrich filtered signals with supporting data via dispatched gatherers.',
            '4_investigate': 'Generate human-readable issue / explanation / recommended_action.',
        },
        'signal_types': signal_types,
        'thresholds':   _build_thresholds(),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

OUTPUT_PATH = _SI_PKG / 'mcp' / 'app' / 'pipeline_catalog.json'


def main() -> None:
    catalog = build_catalog()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    n_detectors = sum(len(v['detectors']) for v in catalog['signal_types'].values())
    n_gatherers = sum(len(v['gatherers']) for v in catalog['signal_types'].values())
    print(
        f"Wrote {OUTPUT_PATH.relative_to(_REPO_ROOT)} — "
        f"{len(catalog['signal_types'])} signal types, "
        f"{n_detectors} detectors, "
        f"{n_gatherers} gatherer dispatches, "
        f"{len(catalog['thresholds'])} threshold fields."
    )


if __name__ == '__main__':
    main()
