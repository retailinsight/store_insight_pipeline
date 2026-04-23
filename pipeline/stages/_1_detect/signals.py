"""
Signal Factories
================
Central definitions for every signal type produced by the detection stage.

Each factory function returns a fully-formed signal dict.  Detectors call
the relevant factory rather than constructing dicts inline, so the shape of
each signal type is defined and maintained in exactly one place.

Adding a new signal type
------------------------
1. Add a new ``TypedDict`` class for the signal shape.
2. Add a new ``make_<type>_signal(...)`` factory function returning that type.
3. Use it in the corresponding detector module.

The ``merge_key`` embedded in each signal controls merging in ``detect.py``:
signals that share a key are merged into one; signals with unique keys pass
through untouched.
"""

from __future__ import annotations

from typing import TypedDict

# ---------------------------------------------------------------------------
# Signal type definitions
# ---------------------------------------------------------------------------

class OsaSignal(TypedDict):
    """Typed shape for an OSA-type detection signal."""
    signal_type:         str                    # always 'OSA'
    merge_key:           tuple[str, int, str]   # ('OSA', store_id, department)
    store_id:            int
    department:          str
    trigger_types:       list[str]
    this_week_lsv:       float | None
    last_week_osa:       float | None
    this_week_osa:       float | None
    wow_drift_pp:        float | None
    chain_this_week_osa: float | None
    chain_gap_pp:        float | None
    chain_wow_drift_pp:  float | None
    repeat_item_count:   int | None
    repeat_item_details: list[dict]


class ComplianceSignal(TypedDict):
    """Typed shape for a compliance-type detection signal."""
    signal_type:       str                # always 'COMPLIANCE'
    merge_key:         tuple[str, int]    # ('COMPLIANCE', store_id)
    store_id:          int
    site_name:         str
    trigger_types:     list[str]
    this_week_worked:  int
    this_week_tf:      int
    this_week_tf_rate: float
    last_week_worked:  int
    last_week_tf:      int
    last_week_tf_rate: float
    tf_rate_change:    float
    chain_tf_rate:     float
    above_chain_by:    float


class MarkdownOverrideSignal(TypedDict):
    """Typed shape for a markdown-override detection signal."""
    signal_type:              str                  # always 'MARKDOWN_OVERRIDE'
    merge_key:                tuple[str, int]      # ('MARKDOWN_OVERRIDE', store_id)
    store_id:                 int
    site_name:                str
    trigger_types:            list[str]
    this_week_override_rate:  float
    last_week_override_rate:  float | None
    wow_change_pp:            float | None
    chain_override_rate:      float | None
    above_chain_pp:           float | None
    this_week_total_markdowns: int
    this_week_overrides:      int


class WasteSignal(TypedDict):
    """Typed shape for a waste (straight-to-bin) detection signal."""
    signal_type:          str                      # always 'WASTE'
    merge_key:            tuple[str, int]           # ('WASTE', store_id)
    store_id:             int
    site_name:            str
    trigger_types:        list[str]
    this_week_stb_rate:   float
    last_week_stb_rate:   float | None
    wow_change_pp:        float | None
    chain_stb_rate:       float | None
    above_chain_pp:       float | None
    this_week_waste_qty:  int
    this_week_stb_qty:    int
    this_week_waste_value: float


class MarkdownSellthroughSignal(TypedDict):
    """Typed shape for a markdown sell-through detection signal."""
    signal_type:                str                # always 'MARKDOWN_SELLTHROUGH'
    merge_key:                  tuple[str, int]    # ('MARKDOWN_SELLTHROUGH', store_id)
    store_id:                   int
    site_name:                  str
    trigger_types:              list[str]
    this_week_sellthrough_rate: float
    last_week_sellthrough_rate: float | None
    wow_change_pp:              float | None
    chain_sellthrough_rate:     float | None
    below_chain_pp:             float | None
    this_week_markdown_qty:     int
    this_week_markdown_value:   float


class MarkdownSkuSignal(TypedDict):
    """Typed shape for a SKU-level markdown detection signal."""
    signal_type:            str                        # always 'MARKDOWN_SKU'
    merge_key:              tuple[str, int, int]       # ('MARKDOWN_SKU', store_id, item_id)
    store_id:               int
    site_name:              str
    item_id:                int
    item_description:       str
    department:             str
    trigger_types:          list[str]
    markdown_request_count: int | None
    override_count:         int | None
    lookback_weeks:         int
    avg_markdown_pct:       float | None


Signal = (
    OsaSignal
    | ComplianceSignal
    | MarkdownOverrideSignal
    | WasteSignal
    | MarkdownSellthroughSignal
    | MarkdownSkuSignal
)


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

def make_osa_signal(
    store_id: int,
    department: str,
    trigger_types: list[str],
    this_week_lsv: float | None = None,
    last_week_osa: float | None = None,
    this_week_osa: float | None = None,
    wow_drift_pp: float | None = None,
    chain_this_week_osa: float | None = None,
    chain_gap_pp: float | None = None,
    chain_wow_drift_pp: float | None = None,
    repeat_item_count: int | None = None,
    repeat_item_details: list[dict] | None = None,
) -> OsaSignal:
    """
    Build a signal dict for an OSA-type alert.

    Parameters
    ----------
    store_id             : int
    department           : str — e.g. 'CHILLED'
    trigger_types        : list[str] — e.g. ['WOW']
    this_week_lsv        : float | None — £ lost sales this week
    last_week_osa        : float | None — OSA % last week
    this_week_osa        : float | None — OSA % this week
    wow_drift_pp         : float | None — WoW OSA change in pp
    chain_this_week_osa  : float | None — chain average OSA % this week
    chain_gap_pp         : float | None — gap vs chain in pp (negative = below)
    chain_wow_drift_pp   : float | None — chain WoW OSA drift in pp
    repeat_item_count    : int | None — number of repeat-offender items
    repeat_item_details  : list | None — per-item repeat detail dicts
    """
    return {
        'signal_type':         'OSA',
        'merge_key':           ('OSA', store_id, department),
        'store_id':            store_id,
        'department':          department,
        'trigger_types':       list(trigger_types),
        'this_week_lsv':       this_week_lsv,
        'last_week_osa':       last_week_osa,
        'this_week_osa':       this_week_osa,
        'wow_drift_pp':        wow_drift_pp,
        'chain_this_week_osa': chain_this_week_osa,
        'chain_gap_pp':        chain_gap_pp,
        'chain_wow_drift_pp':  chain_wow_drift_pp,
        'repeat_item_count':   repeat_item_count,
        'repeat_item_details': repeat_item_details if repeat_item_details is not None else [],
    }


def make_markdown_override_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_week_override_rate: float = 0.0,
    last_week_override_rate: float | None = None,
    wow_change_pp: float | None = None,
    chain_override_rate: float | None = None,
    above_chain_pp: float | None = None,
    this_week_total_markdowns: int = 0,
    this_week_overrides: int = 0,
) -> MarkdownOverrideSignal:
    """
    Build a signal dict for a markdown-override alert.

    Parameters
    ----------
    store_id                  : int
    trigger_types             : list[str] — e.g. ['VS_CHAIN'] or ['WOW']
    site_name                 : str | None — human-readable store name
    this_week_override_rate   : float — override % this week (0–100)
    last_week_override_rate   : float | None — override % last week
    wow_change_pp             : float | None — WoW change in pp
    chain_override_rate       : float | None — chain average override %
    above_chain_pp            : float | None — pp above chain average
    this_week_total_markdowns : int — total markdowns this week
    this_week_overrides       : int — overridden markdowns this week
    """
    return {
        'signal_type':              'MARKDOWN_OVERRIDE',
        'merge_key':                ('MARKDOWN_OVERRIDE', store_id),
        'store_id':                 store_id,
        'site_name':                site_name or f'Store {store_id}',
        'trigger_types':            list(trigger_types),
        'this_week_override_rate':  this_week_override_rate,
        'last_week_override_rate':  last_week_override_rate,
        'wow_change_pp':            wow_change_pp,
        'chain_override_rate':      chain_override_rate,
        'above_chain_pp':           above_chain_pp,
        'this_week_total_markdowns': this_week_total_markdowns,
        'this_week_overrides':      this_week_overrides,
    }


def make_waste_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_week_stb_rate: float = 0.0,
    last_week_stb_rate: float | None = None,
    wow_change_pp: float | None = None,
    chain_stb_rate: float | None = None,
    above_chain_pp: float | None = None,
    this_week_waste_qty: int = 0,
    this_week_stb_qty: int = 0,
    this_week_waste_value: float = 0.0,
) -> WasteSignal:
    """
    Build a signal dict for a waste (straight-to-bin) alert.

    Parameters
    ----------
    store_id              : int
    trigger_types         : list[str] — e.g. ['VS_CHAIN'] or ['WOW']
    site_name             : str | None — human-readable store name
    this_week_stb_rate    : float — straight-to-bin % this week (0–100)
    last_week_stb_rate    : float | None — STB % last week
    wow_change_pp         : float | None — WoW change in pp
    chain_stb_rate        : float | None — chain average STB %
    above_chain_pp        : float | None — pp above chain average
    this_week_waste_qty   : int — total units wasted this week
    this_week_stb_qty     : int — units straight-to-bin this week
    this_week_waste_value : float — £ value of waste this week
    """
    return {
        'signal_type':          'WASTE',
        'merge_key':            ('WASTE', store_id),
        'store_id':             store_id,
        'site_name':            site_name or f'Store {store_id}',
        'trigger_types':        list(trigger_types),
        'this_week_stb_rate':   this_week_stb_rate,
        'last_week_stb_rate':   last_week_stb_rate,
        'wow_change_pp':        wow_change_pp,
        'chain_stb_rate':       chain_stb_rate,
        'above_chain_pp':       above_chain_pp,
        'this_week_waste_qty':  this_week_waste_qty,
        'this_week_stb_qty':    this_week_stb_qty,
        'this_week_waste_value': this_week_waste_value,
    }


def make_markdown_sellthrough_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_week_sellthrough_rate: float = 0.0,
    last_week_sellthrough_rate: float | None = None,
    wow_change_pp: float | None = None,
    chain_sellthrough_rate: float | None = None,
    below_chain_pp: float | None = None,
    this_week_markdown_qty: int = 0,
    this_week_markdown_value: float = 0.0,
) -> MarkdownSellthroughSignal:
    """
    Build a signal dict for a markdown sell-through alert.

    Parameters
    ----------
    store_id                    : int
    trigger_types               : list[str] — e.g. ['VS_CHAIN'] or ['WOW']
    site_name                   : str | None — human-readable store name
    this_week_sellthrough_rate  : float — sell-through % this week (0–100)
    last_week_sellthrough_rate  : float | None — sell-through % last week
    wow_change_pp               : float | None — WoW change in pp
    chain_sellthrough_rate      : float | None — chain average sell-through %
    below_chain_pp              : float | None — pp below chain average
    this_week_markdown_qty      : int — markdown units this week
    this_week_markdown_value    : float — £ markdown sales this week
    """
    return {
        'signal_type':                'MARKDOWN_SELLTHROUGH',
        'merge_key':                  ('MARKDOWN_SELLTHROUGH', store_id),
        'store_id':                   store_id,
        'site_name':                  site_name or f'Store {store_id}',
        'trigger_types':              list(trigger_types),
        'this_week_sellthrough_rate': this_week_sellthrough_rate,
        'last_week_sellthrough_rate': last_week_sellthrough_rate,
        'wow_change_pp':              wow_change_pp,
        'chain_sellthrough_rate':     chain_sellthrough_rate,
        'below_chain_pp':             below_chain_pp,
        'this_week_markdown_qty':     this_week_markdown_qty,
        'this_week_markdown_value':   this_week_markdown_value,
    }


def make_markdown_sku_signal(
    store_id: int,
    item_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    item_description: str = '',
    department: str = '',
    markdown_request_count: int | None = None,
    override_count: int | None = None,
    lookback_weeks: int = 4,
    avg_markdown_pct: float | None = None,
) -> MarkdownSkuSignal:
    """
    Build a signal dict for a SKU-level markdown alert.

    Parameters
    ----------
    store_id               : int
    item_id                : int
    trigger_types          : list[str] — e.g. ['REPEAT_REQUEST'] or ['EXCESSIVE_OVERRIDE']
    site_name              : str | None — human-readable store name
    item_description       : str — human-readable item name
    department             : str — department name
    markdown_request_count : int | None — times this SKU was marked down in the window
    override_count         : int | None — times this SKU's markdown was overridden
    lookback_weeks         : int — rolling window length
    avg_markdown_pct       : float | None — average markdown depth %
    """
    return {
        'signal_type':            'MARKDOWN_SKU',
        'merge_key':              ('MARKDOWN_SKU', store_id, item_id),
        'store_id':               store_id,
        'site_name':              site_name or f'Store {store_id}',
        'item_id':                item_id,
        'item_description':       item_description,
        'department':             department,
        'trigger_types':          list(trigger_types),
        'markdown_request_count': markdown_request_count,
        'override_count':         override_count,
        'lookback_weeks':         lookback_weeks,
        'avg_markdown_pct':       avg_markdown_pct,
    }


def make_compliance_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_week_worked: int = 0,
    this_week_tf: int = 0,
    this_week_tf_rate: float = 0.0,
    last_week_worked: int = 0,
    last_week_tf: int = 0,
    last_week_tf_rate: float = 0.0,
    tf_rate_change: float = 0.0,
    chain_tf_rate: float = 0.0,
    above_chain_by: float = 0.0,
) -> ComplianceSignal:
    """
    Build a signal dict for a compliance-type alert.

    Parameters
    ----------
    store_id           : int
    trigger_types      : list[str] — e.g. ['TICK_AND_FLICK']
    site_name          : str | None — human-readable store name
    this_week_worked   : int — alerts worked this week
    this_week_tf       : int — tick-and-flick count this week
    this_week_tf_rate  : float — tick-and-flick rate % this week
    last_week_worked   : int — alerts worked last week
    last_week_tf       : int — tick-and-flick count last week
    last_week_tf_rate  : float — tick-and-flick rate % last week
    tf_rate_change     : float — pp change in TF rate WoW
    chain_tf_rate      : float — chain-wide TF rate % this week
    above_chain_by     : float — pp above chain average
    """
    return {
        'signal_type':       'COMPLIANCE',
        'merge_key':         ('COMPLIANCE', store_id),
        'store_id':          store_id,
        'site_name':         site_name or f'Store {store_id}',
        'trigger_types':     list(trigger_types),
        'this_week_worked':  this_week_worked,
        'this_week_tf':      this_week_tf,
        'this_week_tf_rate': this_week_tf_rate,
        'last_week_worked':  last_week_worked,
        'last_week_tf':      last_week_tf,
        'last_week_tf_rate': last_week_tf_rate,
        'tf_rate_change':    tf_rate_change,
        'chain_tf_rate':     chain_tf_rate,
        'above_chain_by':    above_chain_by,
    }
