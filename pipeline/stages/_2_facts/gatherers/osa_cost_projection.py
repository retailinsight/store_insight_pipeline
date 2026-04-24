"""
Fact Gatherer: Cost-of-Doing-Nothing Projection
================================================
Pure-Python gatherer that computes a forward projection of lost sales
based on the signal's ``this_week_lsv`` and a configurable number of
projection weeks.

No Snowpark query is needed — all inputs come from the signal dict and
pipeline parameters.

Signal types : OSA
Facts key    : cost_projection, projection_weeks

Public API
----------
    gather(signals) -> {}
    extract_facts(signal, raw_result, projection_weeks) -> dict
"""

from store_insight.pipeline.stages._2_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'osa_cost_projection',
    signal_types = ['OSA'],
    facts_keys   = ['cost_projection', 'projection_weeks'],
    description  = 'Cost-of-doing-nothing projection: this_week_lsv * projection_weeks.',
)


def gather(signals):
    """No batch query needed — facts are derived per-signal in extract_facts."""
    return {}


def extract_facts(signal, raw_result, projection_weeks=4):
    """Compute cost projection from the signal's this-week LSV."""
    lsv = signal.get('this_week_lsv') or 0
    return {
        'cost_projection':  round(lsv * projection_weeks, 2),
        'projection_weeks': projection_weeks,
    }
