from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='osa_big_drop',
    signal_type='OSA_BIG_DROP',
    formula='this_week_lsv.store_controlled',
    description='Store-controlled lost sales value on the sales day.',
)


def projected_cost(signal: dict, context: dict | None = None) -> float:
    return float((signal.get('this_week_lsv') or {}).get('store_controlled') or 0)
