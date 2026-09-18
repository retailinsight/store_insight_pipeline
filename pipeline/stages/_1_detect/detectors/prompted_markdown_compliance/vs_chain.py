"""
Detector: VS_CHAIN (Prompted markdown compliance below chain average)
=====================================================================
Fires when a store's prompted-markdown on-time actioned rate is at least
``min_prompted_markdown_compliance_chain_gap`` percentage points below the
chain-wide average AND the store had at least
``min_prompted_markdown_compliance_volume`` prompts issued this week.

Data source: a canonical DataFrame with columns:
    ALERT_DATE, STORE_ID, ITEM_HIERARCHY_2, COMPLIANT

Public API
----------
    detect(prompted_compliance, this_week_start, this_week_end,
           min_prompted_markdown_compliance_chain_gap,
           min_prompted_markdown_compliance_volume, store_id)
    -> list[signal]
"""

from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.prompted_markdown_compliance._core import (
    _chain_avg_volume,
    _chain_rate,
    _make_signal_for_store,
    _weekly_store_rates,
)

METADATA = DetectorInfo(
    name='VS_CHAIN',
    problem="A store's prompted-markdown on-time actioned rate is below the chain average.",
    action='Investigate why this store is actioning fewer prompts on time than its peers.',
    baseline='The chain-wide prompted-markdown on-time actioned rate for the same calendar week.',
    logic=(
        'Prompted markdown compliance rate = prompts actioned on time / prompts issued.\n'
        'Below-chain gap = chain_rate - store_rate (as a ratio).\n'
        'Fires when gap >= min_prompted_markdown_compliance_chain_gap and this_week_prompts_issued >= min_prompted_markdown_compliance_volume.'
    ),
    config_keys=['min_prompted_markdown_compliance_chain_gap', 'min_prompted_markdown_compliance_volume'],
)


def detect(
    prompted_compliance=None,
    this_week_start=None,
    this_week_end=None,
    last_week_start=None,
    last_week_end=None,
    min_prompted_markdown_compliance_chain_gap=0.05,
    min_prompted_markdown_compliance_volume=50,
    store_id=None,
):
    """
    Detect stores whose prompted-markdown compliance rate is below the chain average.

    Parameters
    ----------
    prompted_compliance                     : Snowpark-like DataFrame with canonical columns:
                                              ALERT_DATE, STORE_ID, ITEM_HIERARCHY_2, COMPLIANT
    this_week_start/end                     : date strings (YYYY-MM-DD) for the current week
    last_week_start/end                     : date strings (YYYY-MM-DD) for the previous week
                                            (required for workload classification)
    min_prompted_markdown_compliance_chain_gap : minimum ratio below chain to fire (default: 0.05 = 5pp)
    min_prompted_markdown_compliance_volume    : minimum prompts issued this week to qualify (default: 50)
    store_id                                : optional int or list[int] — restrict to specific stores

    Returns
    -------
    list of PROMPTED_MARKDOWN_COMPLIANCE signal dicts
    """
    if prompted_compliance is None:
        return []
    rows = [r.as_dict() if hasattr(r, 'as_dict') else r for r in prompted_compliance.collect()]

    if store_id is not None:
        if not isinstance(store_id, list | tuple | set):
            store_id = {store_id}
        else:
            store_id = set(store_id)
        rows = [r for r in rows if int(r['STORE_ID']) in store_id]

    this_weekly = _weekly_store_rates(rows, this_week_start, this_week_end)
    last_weekly = _weekly_store_rates(rows, last_week_start, last_week_end)
    chain_rate = _chain_rate(this_weekly)
    chain_avg_volume = _chain_avg_volume(this_weekly)

    signals = []
    for sid, this in this_weekly.items():
        if this['prompts_issued'] < min_prompted_markdown_compliance_volume:
            continue
        gap = chain_rate - this['compliance_rate']
        if gap < min_prompted_markdown_compliance_chain_gap:
            continue
        signals.append(_make_signal_for_store(
            store_id=sid,
            this=this,
            last=last_weekly.get(sid),
            chain_rate=chain_rate,
            chain_avg_volume=chain_avg_volume,
            trigger_types=['VS_CHAIN'],
        ))

    print(f'[1_detect] PROMPTED_MARKDOWN_COMPLIANCE VS_CHAIN={len(signals)}')
    return signals
