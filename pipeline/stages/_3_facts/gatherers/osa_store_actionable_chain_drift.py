"""
Fact Gatherer: OSA_STORE_ACTIONABLE Chain Drift (store-controlled)
==================================================================
For each department that appears in an OSA_STORE_ACTIONABLE signal, returns
the chain-wide *store-controlled* OSA for last week, this week, and the
drift between them.  This contextualises whether a store is under-performing
a chain-wide store-controlled benchmark.

Only departments with chain data that passes the configured quality thresholds
are returned.

Signal types : OSA_STORE_ACTIONABLE
Facts keys   : chain_store_last_week_osa, chain_store_this_week_osa,
               chain_store_drift_pp

Public API
----------
    gather(osa, signals, last_week_start, last_week_end,
           this_week_start, this_week_end, dept_col,
           min_actionable_positive_rows, max_actionable_unknown_row_pct)
    -> dict keyed by department name
"""

from __future__ import annotations

from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import (
    actionable_window_metrics as window_metrics,
)
from store_insight.pipeline.pipeline._shared import quality_is_valid, quality_values
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name='osa_store_actionable_chain_drift',
    signal_types=['OSA_STORE_ACTIONABLE'],
    facts_keys=[
        'chain_store_last_week_osa',
        'chain_store_this_week_osa',
        'chain_store_drift_pp',
    ],
    description=(
        'Chain-wide store-controlled OSA drift per department, '
        'returned only when data-quality thresholds are met.'
    ),
)


def gather(
    osa,
    signals,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    dept_col='ITEM_HIERARCHY_2',
    min_actionable_positive_rows=10,
    max_actionable_unknown_row_pct=10.0,
):
    """
    Return chain-wide store-controlled OSA drift for each signal department.

    Parameters
    ----------
    osa              : Snowpark DataFrame — must be the *full* chain DataFrame
    signals          : list of OSA_STORE_ACTIONABLE signal dicts
    last_week_start/end, this_week_start/end : date strings (YYYY-MM-DD)
    dept_col         : department column name
    min_actionable_positive_rows     : minimum positive-inventory rows for a valid chain window
    max_actionable_unknown_row_pct   : maximum unknown-inventory row percentage for a valid window

    Returns
    -------
    dict keyed by department name ->
        {
            'chain_store_last_week_osa': float,
            'chain_store_this_week_osa': float,
            'chain_store_drift_pp':      float,
        }
    """
    if not signals:
        return {}

    depts = list({sig.get('department') for sig in signals if sig.get('department')})
    if not depts:
        return {}

    dept_filter = F.col(dept_col).isin(depts)

    group_cols = [dept_col]
    last = window_metrics(
        osa.filter(dept_filter),
        last_week_start,
        last_week_end,
        group_cols,
        'LAST',
    )
    this = window_metrics(
        osa.filter(dept_filter),
        this_week_start,
        this_week_end,
        group_cols,
        'THIS',
    )

    joined = last.join(this, on=group_cols, how='inner')

    result = {}
    for r in joined.collect():
        last_quality = quality_values(r, 'LAST')
        this_quality = quality_values(r, 'THIS')
        if not (
            quality_is_valid(last_quality, min_actionable_positive_rows, max_actionable_unknown_row_pct)
            and quality_is_valid(this_quality, min_actionable_positive_rows, max_actionable_unknown_row_pct)
        ):
            continue

        dept = r[dept_col]
        last_osa = float(r['LAST_STORE_OSA'] or 0) * 100
        this_osa = float(r['THIS_STORE_OSA'] or 0) * 100
        result[dept] = {
            'chain_store_last_week_osa': round(last_osa, 2),
            'chain_store_this_week_osa': round(this_osa, 2),
            'chain_store_drift_pp': round(this_osa - last_osa, 2),
        }
    return result


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    dept = signal.get('department', '')
    chain = raw_result.get(dept, {})
    return {
        'chain_store_last_week_osa': chain.get('chain_store_last_week_osa'),
        'chain_store_this_week_osa': chain.get('chain_store_this_week_osa'),
        'chain_store_drift_pp': chain.get('chain_store_drift_pp'),
    }
