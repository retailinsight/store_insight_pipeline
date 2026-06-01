"""
Fact Gatherer: Chain-level Week-on-Week OSA Drift
==================================================
For each department that appears in the signal list, returns the chain-wide
OSA for last week, this week, and the drift between them.

This contextualises store-level WoW drops: if the chain also dropped in the
same department, the store may be moving with a market-wide pattern rather
than experiencing an isolated problem.

Important: always pass the *full* OSA DataFrame (not a store-filtered subset)
so that chain averages reflect the whole estate.

Signal types : OSA
Facts key    : chain_last_week_osa, chain_this_week_osa, chain_drift_pp

Public API
----------
    gather(osa, signals, last_week_start, last_week_end,
           this_week_start, this_week_end, dept_col)
    -> dict keyed by department name
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._3_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'osa_chain_drift',
    signal_types = ['OSA'],
    facts_keys   = ['chain_last_week_osa', 'chain_this_week_osa', 'chain_drift_pp'],
    description  = 'Chain-wide WoW OSA drift per department, keyed by department name.',
)


def gather(
    osa,
    signals,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    dept_col='ITEM_HIERARCHY_2',
):
    """
    Return chain-wide WoW OSA drift per department for all departments
    that appear in ``signals``.

    Parameters
    ----------
    osa              : Snowpark DataFrame — must be the *full* chain DataFrame
    signals          : list of signal dicts (from Stage 1)
    last_week_start/end : date strings for the previous week
    this_week_start/end : date strings for the current week
    dept_col         : department column name

    Returns
    -------
    dict keyed by department name ->
        {
            'chain_last_week_osa': float,   # % e.g. 89.3
            'chain_this_week_osa': float,
            'chain_drift_pp':      float,   # signed pp change
        }
    """
    if not signals:
        return {}

    depts = list({sig['department'] for sig in signals if sig.get('department')})
    if not depts:
        return {}

    dept_filter = None
    for d in depts:
        c = F.col(dept_col) == d
        dept_filter = c if dept_filter is None else dept_filter | c

    def _chain_score(start, end, prefix):
        return (
            osa
            .filter((F.col('DATE') >= start) & (F.col('DATE') <= end))
            .filter(dept_filter)
            .group_by(dept_col)
            .agg(
                F.sum('ACTUAL_SALES_VOLUME').alias(f'{prefix}_SALES'),
                F.sum('LOST_SALES_VOLUME').alias(f'{prefix}_LSV'),
            )
            .with_column(
                f'{prefix}_OSA',
                F.when(
                    F.col(f'{prefix}_SALES') + F.col(f'{prefix}_LSV') != 0,
                    F.col(f'{prefix}_SALES') / (F.col(f'{prefix}_SALES') + F.col(f'{prefix}_LSV')),
                ).otherwise(0),
            )
        )

    last = _chain_score(last_week_start, last_week_end, 'LAST')
    this = _chain_score(this_week_start, this_week_end, 'THIS')

    joined = (
        last
        .join(this, on=[dept_col], how='inner')
        .with_column('CHAIN_DRIFT', F.col('THIS_OSA') - F.col('LAST_OSA'))
    )

    result = {}
    for r in joined.collect():
        result[r[dept_col]] = {
            'chain_last_week_osa': round(float(r['LAST_OSA'] or 0) * 100, 2),
            'chain_this_week_osa': round(float(r['THIS_OSA'] or 0) * 100, 2),
            'chain_drift_pp':      round(float(r['CHAIN_DRIFT'] or 0) * 100, 2),
        }
    return result


def extract_facts(signal, raw_result):
    """Extract per-signal facts from the batch gather result."""
    dept = signal.get('department', '')
    chain = raw_result.get(dept, {})
    return {
        'chain_last_week_osa': chain.get('chain_last_week_osa'),
        'chain_this_week_osa': chain.get('chain_this_week_osa'),
        'chain_drift_pp':      chain.get('chain_drift_pp'),
    }
