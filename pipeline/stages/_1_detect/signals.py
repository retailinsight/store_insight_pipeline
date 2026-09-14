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


class OsaStoreActionableSignal(TypedDict):
    """Typed shape for an actionable OSA detection signal."""
    signal_type:                 str
    merge_key:                   tuple[str, int, str]
    store_id:                    int
    department:                  str
    trigger_types:               list[str]
    last_week_osa:               float | None
    this_week_osa:               float | None
    total_last_week_osa:         float | None
    total_this_week_osa:         float | None
    wow_drift_pp:                float | None
    chain_this_week_osa:         float | None
    total_chain_this_week_osa:   float | None
    chain_gap_pp:                float | None
    last_week_lsv:               dict | None
    this_week_lsv:               dict
    lsv_change:                  dict | None
    quality:                     dict


class OsaBigDropSignal(TypedDict):
    """Typed shape for a day-on-day OSA big-drop detection signal."""
    signal_type:                 str
    merge_key:                   tuple[str, int, str]
    store_id:                    int
    department:                  str
    trigger_types:               list[str]
    last_week_osa:               float | None
    this_week_osa:               float | None
    total_last_week_osa:         float | None
    total_this_week_osa:         float | None
    wow_drift_pp:                float | None
    chain_this_week_osa:         float | None
    total_chain_this_week_osa:   float | None
    chain_gap_pp:                float | None
    last_week_lsv:               dict | None
    this_week_lsv:               dict
    lsv_change:                  dict | None
    latest_day:                  str | None
    prior_day:                   str | None
    quality:                     dict


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
    workload:          dict


class MarkdownComplianceSignal(TypedDict):
    """Typed shape for a markdown-compliance detection signal."""
    signal_type:                    str                # always 'MARKDOWN_COMPLIANCE'
    merge_key:                      tuple[str, int]    # ('MARKDOWN_COMPLIANCE', store_id)
    store_id:                       int
    site_name:                      str
    trigger_types:                  list[str]
    this_week_markdowns_due:        int
    this_week_completed_on_time:    int
    this_week_compliance_rate:      float
    last_week_compliance_rate:      float | None
    wow_change_pp:                  float | None
    chain_compliance_rate:          float | None
    below_chain_pp:                 float | None
    this_week_at_risk_value:        float            # internal projected-cost basis
    workload:                       dict


class ExpiryDateComplianceSignal(TypedDict):
    """Typed shape for an expiry-date-compliance detection signal."""
    signal_type: str
    merge_key: tuple[str, int]
    store_id: int
    site_name: str
    trigger_types: list[str]
    trailing_7d_compliance_rate: float
    prev_7d_compliance_rate: float | None
    change_pp: float | None
    chain_trailing_7d_compliance_rate: float | None
    below_chain_pp: float | None
    chain_change_pp: float | None
    trailing_7d_checks_due: int
    trailing_7d_checks_completed: int
    trailing_7d_at_risk_value: float
    workload: dict


class PromptedMarkdownComplianceSignal(TypedDict):
    """Typed shape for a prompted-markdown-compliance detection signal."""
    signal_type: str                # always 'PROMPTED_MARKDOWN_COMPLIANCE'
    merge_key: tuple[str, int]      # ('PROMPTED_MARKDOWN_COMPLIANCE', store_id)
    store_id: int
    site_name: str
    trigger_types: list[str]
    this_week_prompts_issued: int
    this_week_prompts_actioned_on_time: int
    this_week_compliance_rate: float
    last_week_compliance_rate: float | None
    wow_change_pp: float | None
    chain_compliance_rate: float | None
    below_chain_pp: float | None
    median_response_minutes: float | None
    this_week_at_risk_value: float  # internal projected-cost basis
    workload: dict


class BigDropPromptedMarkdownComplianceSignal(TypedDict):
    """Typed shape for a day-on-day prompted-markdown-compliance big-drop signal."""
    signal_type: str                # always 'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE'
    merge_key: tuple[str, int]      # ('BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE', store_id)
    store_id: int
    site_name: str
    trigger_types: list[str]
    this_day_prompts_issued: int
    this_day_prompts_actioned_on_time: int
    this_day_compliance_rate: float
    prev_day_compliance_rate: float | None
    drop_pp: float | None
    chain_compliance_rate: float | None
    below_chain_pp: float | None
    median_response_minutes: float | None
    this_day_at_risk_value: float
    workload: dict


class BigDropMarkdownComplianceSignal(TypedDict):
    """Typed shape for a day-on-day markdown-compliance big-drop signal."""
    signal_type: str                # always 'BIG_DROP_MARKDOWN_COMPLIANCE'
    merge_key: tuple[str, int]      # ('BIG_DROP_MARKDOWN_COMPLIANCE', store_id)
    store_id: int
    site_name: str
    trigger_types: list[str]
    this_day_markdowns_due: int
    this_day_completed_on_time: int
    this_day_compliance_rate: float
    prev_day_compliance_rate: float | None
    drop_pp: float | None
    chain_compliance_rate: float | None
    below_chain_pp: float | None
    this_day_at_risk_value: float
    workload: dict


class BigDropExpiryDateComplianceSignal(TypedDict):
    """Typed shape for a day-on-day expiry-date-compliance big-drop signal."""
    signal_type: str                # always 'BIG_DROP_EXPIRY_DATE_COMPLIANCE'
    merge_key: tuple[str, int]      # ('BIG_DROP_EXPIRY_DATE_COMPLIANCE', store_id)
    store_id: int
    site_name: str
    trigger_types: list[str]
    this_day_checks_due: int
    this_day_checks_completed: int
    this_day_compliance_rate: float
    prev_day_compliance_rate: float | None
    drop_pp: float | None
    chain_compliance_rate: float | None
    below_chain_pp: float | None
    this_day_at_risk_value: float
    workload: dict


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


class OsaRecurringSlotSignal(TypedDict):
    """Typed shape for a recurring OSA slot detection signal."""
    signal_type:            str                              # always 'OSA_RECURRING_SLOT'
    merge_key:              tuple[str, int, str, int, int]   # (type, store_id, department, dow, period_id)
    store_id:               int
    department:             str
    section:                str                              # encoded alert section, e.g. 'Produce|Monday|Morning'
    trigger_types:          list[str]
    dow:                    int
    dow_name:               str
    period_id:              int
    period_label:           str
    repeat_item_count:      int
    repeat_item_details:    list[dict]
    total_lsv:              float
    avg_weekly_lsv:         float


class MarkdownSkuSignal(TypedDict):
    """Typed shape for a SKU-level markdown detection signal."""
    signal_type:            str                        # always 'MARKDOWN_SKU'
    merge_key:              tuple[str, int, int]       # ('MARKDOWN_SKU', store_id, item_id)
    store_id:               int
    site_name:              str
    item_id:                int
    item_description:       str
    department:             str
    section:                str                        # encoded alert section, e.g. 'Produce|12345'
    trigger_types:          list[str]
    markdown_request_count: int | None
    override_count:         int | None
    lookback_weeks:         int
    avg_markdown_pct:       float | None


class WasteTrimSignal(TypedDict):
    """Typed shape for a waste-trim detection signal."""
    signal_type:      str                      # always 'WASTE_TRIM'
    merge_key:        tuple[str, int, int]     # ('WASTE_TRIM', store_id, item_id)
    store_id:         int
    site_name:        str
    item_id:          int
    item_description: str
    department:       str
    section:          str                    # encoded alert section, e.g. 'Produce|12345'
    trigger_types:    list[str]
    markdown_units:   int
    total_units:      int
    markdown_ratio:   float
    markdown_value:   float


class StraightToBinSignal(TypedDict):
    """Typed shape for a straight-to-bin value-threshold detection signal."""
    signal_type:                str                    # always 'STRAIGHT_TO_BIN'
    merge_key:                  tuple[str, int]        # ('STRAIGHT_TO_BIN', store_id)
    store_id:                   int
    site_name:                  str
    trigger_types:              list[str]
    threshold_value:            float
    last_week_stb_value:        float
    last_week_stb_items:        int
    chain_avg_stb_value_per_store: float
    vs_chain_multiple:          float


Signal = (
    OsaSignal
    | OsaStoreActionableSignal
    | OsaBigDropSignal
    | OsaRecurringSlotSignal
    | ComplianceSignal
    | MarkdownComplianceSignal
    | PromptedMarkdownComplianceSignal
    | BigDropPromptedMarkdownComplianceSignal
    | BigDropMarkdownComplianceSignal
    | BigDropExpiryDateComplianceSignal
    | MarkdownOverrideSignal
    | WasteSignal
    | MarkdownSellthroughSignal
    | MarkdownSkuSignal
    | WasteTrimSignal
    | StraightToBinSignal
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


def make_osa_store_actionable_signal(
    store_id: int,
    department: str,
    trigger_types: list[str],
    this_week_lsv: dict,
    last_week_lsv: dict | None = None,
    lsv_change: dict | None = None,
    last_week_osa: float | None = None,
    this_week_osa: float | None = None,
    total_last_week_osa: float | None = None,
    total_this_week_osa: float | None = None,
    wow_drift_pp: float | None = None,
    chain_this_week_osa: float | None = None,
    total_chain_this_week_osa: float | None = None,
    chain_gap_pp: float | None = None,
    quality: dict | None = None,
) -> OsaStoreActionableSignal:
    return {
        'signal_type': 'OSA_STORE_ACTIONABLE',
        'merge_key': ('OSA_STORE_ACTIONABLE', store_id, department),
        'store_id': store_id,
        'department': department,
        'trigger_types': list(trigger_types),
        'last_week_osa': last_week_osa,
        'this_week_osa': this_week_osa,
        'total_last_week_osa': total_last_week_osa,
        'total_this_week_osa': total_this_week_osa,
        'wow_drift_pp': wow_drift_pp,
        'chain_this_week_osa': chain_this_week_osa,
        'total_chain_this_week_osa': total_chain_this_week_osa,
        'chain_gap_pp': chain_gap_pp,
        'last_week_lsv': last_week_lsv,
        'this_week_lsv': this_week_lsv,
        'lsv_change': lsv_change,
        'quality': quality or {},
    }


def make_osa_big_drop_signal(
    store_id: int,
    department: str,
    trigger_types: list[str],
    this_week_lsv: dict,
    last_week_lsv: dict | None = None,
    lsv_change: dict | None = None,
    last_week_osa: float | None = None,
    this_week_osa: float | None = None,
    total_last_week_osa: float | None = None,
    total_this_week_osa: float | None = None,
    wow_drift_pp: float | None = None,
    chain_this_week_osa: float | None = None,
    total_chain_this_week_osa: float | None = None,
    chain_gap_pp: float | None = None,
    latest_day: str | None = None,
    prior_day: str | None = None,
    quality: dict | None = None,
) -> OsaBigDropSignal:
    return {
        'signal_type': 'OSA_BIG_DROP',
        'merge_key': ('OSA_BIG_DROP', store_id, department),
        'store_id': store_id,
        'department': department,
        'trigger_types': list(trigger_types),
        'last_week_osa': last_week_osa,
        'this_week_osa': this_week_osa,
        'total_last_week_osa': total_last_week_osa,
        'total_this_week_osa': total_this_week_osa,
        'wow_drift_pp': wow_drift_pp,
        'chain_this_week_osa': chain_this_week_osa,
        'total_chain_this_week_osa': total_chain_this_week_osa,
        'chain_gap_pp': chain_gap_pp,
        'last_week_lsv': last_week_lsv,
        'this_week_lsv': this_week_lsv,
        'lsv_change': lsv_change,
        'latest_day': latest_day,
        'prior_day': prior_day,
        'quality': quality or {},
    }


def make_osa_recurring_slot_signal(
    store_id: int,
    department: str,
    dow: int,
    dow_name: str,
    period_id: int,
    period_label: str,
    repeat_item_count: int,
    repeat_item_details: list[dict],
    total_lsv: float,
    avg_weekly_lsv: float,
    trigger_types: list[str] | None = None,
) -> OsaRecurringSlotSignal:
    """
    Build a signal dict for an OSA recurring-slot alert.

    Parameters
    ----------
    store_id             : int
    department           : str — e.g. 'CHILLED'
    dow                  : int — 1=Sunday … 7=Saturday
    dow_name             : str — e.g. 'Monday'
    period_id            : int — reporting period id
    period_label         : str — e.g. 'Morning (6am-12pm)'
    repeat_item_count    : int — number of repeat-offender items in this slot
    repeat_item_details  : list — per-item detail dicts for this slot
    total_lsv            : float — total £ lost sales across matched items and weeks
    avg_weekly_lsv       : float — average weekly £ lost sales for this slot
    trigger_types        : list[str] — defaults to ['RECURRING_SLOT']
    """
    section = f'{department}|{dow_name}|{period_label}'
    return {
        'signal_type':         'OSA_RECURRING_SLOT',
        'merge_key':           ('OSA_RECURRING_SLOT', store_id, department, dow, period_id),
        'store_id':            store_id,
        'department':          department,
        'section':             section,
        'trigger_types':       list(trigger_types or ['RECURRING_SLOT']),
        'dow':                 dow,
        'dow_name':            dow_name,
        'period_id':           period_id,
        'period_label':        period_label,
        'repeat_item_count':   repeat_item_count,
        'repeat_item_details': repeat_item_details,
        'total_lsv':           total_lsv,
        'avg_weekly_lsv':      avg_weekly_lsv,
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
        'section':                f'{department}|{item_id}',
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
    workload: dict | None = None,
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
    workload           : dict — volume and change classification
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
        'workload':          workload or {},
    }


def make_markdown_compliance_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_week_markdowns_due: int = 0,
    this_week_completed_on_time: int = 0,
    this_week_compliance_rate: float = 0.0,
    last_week_compliance_rate: float | None = None,
    wow_change_pp: float | None = None,
    chain_compliance_rate: float | None = None,
    below_chain_pp: float | None = None,
    this_week_at_risk_value: float = 0.0,
    workload: dict | None = None,
) -> MarkdownComplianceSignal:
    """
    Build a signal dict for a markdown-compliance alert.

    Parameters
    ----------
    store_id                    : int
    trigger_types               : list[str] — e.g. ['WOW'] or ['VS_CHAIN']
    site_name                   : str | None — human-readable store name
    this_week_markdowns_due     : int — markdown tasks due this calendar week
    this_week_completed_on_time : int — markdown tasks completed on time this week
    this_week_compliance_rate   : float — on-time completion % this week (0–100)
    last_week_compliance_rate   : float | None — on-time completion % last week
    wow_change_pp               : float | None — WoW change in percentage points
    chain_compliance_rate       : float | None — chain-wide on-time completion % this week
    below_chain_pp              : float | None — pp below chain average (positive = below)
    this_week_at_risk_value     : float — internal projected-cost basis (£ at risk this week)
    workload                    : dict | None — volume classification evidence
    """
    return {
        'signal_type':                 'MARKDOWN_COMPLIANCE',
        'merge_key':                   ('MARKDOWN_COMPLIANCE', store_id),
        'store_id':                    store_id,
        'site_name':                   site_name or f'Store {store_id}',
        'trigger_types':               list(trigger_types),
        'this_week_markdowns_due':     this_week_markdowns_due,
        'this_week_completed_on_time': this_week_completed_on_time,
        'this_week_compliance_rate':   this_week_compliance_rate,
        'last_week_compliance_rate':   last_week_compliance_rate,
        'wow_change_pp':               wow_change_pp,
        'chain_compliance_rate':       chain_compliance_rate,
        'below_chain_pp':              below_chain_pp,
        'this_week_at_risk_value':     this_week_at_risk_value,
        'workload':                    workload or {},
    }


def make_expiry_date_compliance_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    trailing_7d_compliance_rate: float = 0.0,
    prev_7d_compliance_rate: float | None = None,
    change_pp: float | None = None,
    chain_trailing_7d_compliance_rate: float | None = None,
    below_chain_pp: float | None = None,
    chain_change_pp: float | None = None,
    trailing_7d_checks_due: int = 0,
    trailing_7d_checks_completed: int = 0,
    trailing_7d_at_risk_value: float = 0.0,
    workload: dict | None = None,
) -> ExpiryDateComplianceSignal:
    return {
        'signal_type': 'EXPIRY_DATE_COMPLIANCE',
        'merge_key': ('EXPIRY_DATE_COMPLIANCE', store_id),
        'store_id': store_id,
        'site_name': site_name or f'Store {store_id}',
        'trigger_types': list(trigger_types),
        'trailing_7d_compliance_rate': trailing_7d_compliance_rate,
        'prev_7d_compliance_rate': prev_7d_compliance_rate,
        'change_pp': change_pp,
        'chain_trailing_7d_compliance_rate': chain_trailing_7d_compliance_rate,
        'below_chain_pp': below_chain_pp,
        'chain_change_pp': chain_change_pp,
        'trailing_7d_checks_due': trailing_7d_checks_due,
        'trailing_7d_checks_completed': trailing_7d_checks_completed,
        'trailing_7d_at_risk_value': trailing_7d_at_risk_value,
        'workload': workload or {},
    }


def make_prompted_markdown_compliance_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_week_prompts_issued: int = 0,
    this_week_prompts_actioned_on_time: int = 0,
    this_week_compliance_rate: float = 0.0,
    last_week_compliance_rate: float | None = None,
    wow_change_pp: float | None = None,
    chain_compliance_rate: float | None = None,
    below_chain_pp: float | None = None,
    median_response_minutes: float | None = None,
    this_week_at_risk_value: float = 0.0,
    workload: dict | None = None,
) -> PromptedMarkdownComplianceSignal:
    """
    Build a signal dict for a prompted-markdown-compliance alert.

    Parameters
    ----------
    store_id                         : int
    trigger_types                    : list[str] — e.g. ['WOW'] or ['VS_CHAIN']
    site_name                        : str | None — human-readable store name
    this_week_prompts_issued          : int — prompts issued this calendar week
    this_week_prompts_actioned_on_time : int — prompts actioned on time this week
    this_week_compliance_rate        : float — on-time actioned % this week (0–100)
    last_week_compliance_rate        : float | None — on-time actioned % last week
    wow_change_pp                    : float | None — WoW change in percentage points
    chain_compliance_rate            : float | None — chain-wide on-time actioned % this week
    below_chain_pp                   : float | None — pp below chain average (positive = below)
    median_response_minutes          : float | None — median response time this week in minutes
    this_week_at_risk_value          : float — internal projected-cost basis (£ at risk this week)
    workload                         : dict | None — volume classification evidence
    """
    return {
        'signal_type':                         'PROMPTED_MARKDOWN_COMPLIANCE',
        'merge_key':                           ('PROMPTED_MARKDOWN_COMPLIANCE', store_id),
        'store_id':                            store_id,
        'site_name':                           site_name or f'Store {store_id}',
        'trigger_types':                      list(trigger_types),
        'this_week_prompts_issued':            this_week_prompts_issued,
        'this_week_prompts_actioned_on_time':  this_week_prompts_actioned_on_time,
        'this_week_compliance_rate':           this_week_compliance_rate,
        'last_week_compliance_rate':           last_week_compliance_rate,
        'wow_change_pp':                       wow_change_pp,
        'chain_compliance_rate':               chain_compliance_rate,
        'below_chain_pp':                      below_chain_pp,
        'median_response_minutes':             median_response_minutes,
        'this_week_at_risk_value':             this_week_at_risk_value,
        'workload':                            workload or {},
    }


def make_big_drop_prompted_markdown_compliance_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_day_prompts_issued: int = 0,
    this_day_prompts_actioned_on_time: int = 0,
    this_day_compliance_rate: float = 0.0,
    prev_day_compliance_rate: float | None = None,
    drop_pp: float | None = None,
    chain_compliance_rate: float | None = None,
    below_chain_pp: float | None = None,
    median_response_minutes: float | None = None,
    this_day_at_risk_value: float = 0.0,
    workload: dict | None = None,
) -> BigDropPromptedMarkdownComplianceSignal:
    return {
        'signal_type':                         'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE',
        'merge_key':                           ('BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE', store_id),
        'store_id':                            store_id,
        'site_name':                           site_name or f'Store {store_id}',
        'trigger_types':                       list(trigger_types),
        'this_day_prompts_issued':             this_day_prompts_issued,
        'this_day_prompts_actioned_on_time':   this_day_prompts_actioned_on_time,
        'this_day_compliance_rate':            this_day_compliance_rate,
        'prev_day_compliance_rate':            prev_day_compliance_rate,
        'drop_pp':                             drop_pp,
        'chain_compliance_rate':               chain_compliance_rate,
        'below_chain_pp':                      below_chain_pp,
        'median_response_minutes':             median_response_minutes,
        'this_day_at_risk_value':              this_day_at_risk_value,
        'workload':                            workload or {},
    }


def make_big_drop_markdown_compliance_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_day_markdowns_due: int = 0,
    this_day_completed_on_time: int = 0,
    this_day_compliance_rate: float = 0.0,
    prev_day_compliance_rate: float | None = None,
    drop_pp: float | None = None,
    chain_compliance_rate: float | None = None,
    below_chain_pp: float | None = None,
    this_day_at_risk_value: float = 0.0,
    workload: dict | None = None,
) -> BigDropMarkdownComplianceSignal:
    return {
        'signal_type':                 'BIG_DROP_MARKDOWN_COMPLIANCE',
        'merge_key':                   ('BIG_DROP_MARKDOWN_COMPLIANCE', store_id),
        'store_id':                    store_id,
        'site_name':                   site_name or f'Store {store_id}',
        'trigger_types':               list(trigger_types),
        'this_day_markdowns_due':      this_day_markdowns_due,
        'this_day_completed_on_time':  this_day_completed_on_time,
        'this_day_compliance_rate':    this_day_compliance_rate,
        'prev_day_compliance_rate':    prev_day_compliance_rate,
        'drop_pp':                     drop_pp,
        'chain_compliance_rate':       chain_compliance_rate,
        'below_chain_pp':              below_chain_pp,
        'this_day_at_risk_value':      this_day_at_risk_value,
        'workload':                    workload or {},
    }


def make_big_drop_expiry_date_compliance_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    this_day_checks_due: int = 0,
    this_day_checks_completed: int = 0,
    this_day_compliance_rate: float = 0.0,
    prev_day_compliance_rate: float | None = None,
    drop_pp: float | None = None,
    chain_compliance_rate: float | None = None,
    below_chain_pp: float | None = None,
    this_day_at_risk_value: float = 0.0,
    workload: dict | None = None,
) -> BigDropExpiryDateComplianceSignal:
    return {
        'signal_type':                 'BIG_DROP_EXPIRY_DATE_COMPLIANCE',
        'merge_key':                   ('BIG_DROP_EXPIRY_DATE_COMPLIANCE', store_id),
        'store_id':                    store_id,
        'site_name':                   site_name or f'Store {store_id}',
        'trigger_types':               list(trigger_types),
        'this_day_checks_due':         this_day_checks_due,
        'this_day_checks_completed':   this_day_checks_completed,
        'this_day_compliance_rate':    this_day_compliance_rate,
        'prev_day_compliance_rate':    prev_day_compliance_rate,
        'drop_pp':                     drop_pp,
        'chain_compliance_rate':       chain_compliance_rate,
        'below_chain_pp':              below_chain_pp,
        'this_day_at_risk_value':      this_day_at_risk_value,
        'workload':                    workload or {},
    }


def make_waste_trim_signal(
    store_id: int,
    item_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    item_description: str = '',
    department: str = '',
    markdown_units: int = 0,
    total_units: int = 0,
    markdown_value: float = 0.0,
) -> WasteTrimSignal:
    """
    Build a signal dict for a waste-trim alert.

    Parameters
    ----------
    store_id         : int
    item_id          : int — UPC / WMD item identifier
    trigger_types    : list[str] — e.g. ['WASTE_TRIM']
    site_name        : str | None — human-readable store name
    item_description : str — human-readable item name
    department       : str — department name
    markdown_units   : int — units sold at markdown this week
    total_units      : int — total units sold this week (markdown + full-price)
    markdown_value   : float — £ value of markdown sales this week
    """
    markdown_ratio = round(markdown_units / total_units, 4) if total_units else 0.0
    return {
        'signal_type':      'WASTE_TRIM',
        'merge_key':        ('WASTE_TRIM', store_id, item_id),
        'store_id':         store_id,
        'site_name':        site_name or f'Store {store_id}',
        'item_id':          item_id,
        'item_description': item_description,
        'department':       department,
        'section':          f'{department}|{item_id}',
        'trigger_types':    list(trigger_types),
        'markdown_units':   markdown_units,
        'total_units':      total_units,
        'markdown_ratio':   markdown_ratio,
        'markdown_value':   markdown_value,
    }


def make_straight_to_bin_signal(
    store_id: int,
    trigger_types: list[str],
    site_name: str | None = None,
    threshold_value: float = 100.0,
    last_week_stb_value: float = 0.0,
    last_week_stb_items: int = 0,
    chain_avg_stb_value_per_store: float = 0.0,
    vs_chain_multiple: float = 0.0,
) -> StraightToBinSignal:
    """
    Build a signal dict for a straight-to-bin value-threshold alert.

    Parameters
    ----------
    store_id                      : int
    trigger_types                 : list[str] — e.g. ['VALUE_THRESHOLD']
    site_name                     : str | None — human-readable store name
    threshold_value               : float — £ threshold that triggered the alert
    last_week_stb_value           : float — £ total straight-to-bin value last week
    last_week_stb_items           : int — total items straight-to-bin last week
    chain_avg_stb_value_per_store : float — chain average STB £ per store last week
    vs_chain_multiple             : float — store value / chain average
    """
    return {
        'signal_type':                  'STRAIGHT_TO_BIN',
        'merge_key':                    ('STRAIGHT_TO_BIN', store_id),
        'store_id':                     store_id,
        'site_name':                    site_name or f'Store {store_id}',
        'trigger_types':                list(trigger_types),
        'threshold_value':              threshold_value,
        'last_week_stb_value':          last_week_stb_value,
        'last_week_stb_items':          last_week_stb_items,
        'chain_avg_stb_value_per_store': chain_avg_stb_value_per_store,
        'vs_chain_multiple':            vs_chain_multiple,
    }
