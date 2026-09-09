from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='osa_store_actionable',
    signal_type='OSA_STORE_ACTIONABLE',
    formula='this_week_lsv.store_controlled',
    description='Weekly lost sales value on positive-inventory observations.',
)


def projected_cost(signal: dict, context: dict | None = None) -> float:
    return float((signal.get('this_week_lsv') or {}).get('store_controlled') or 0)
