from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='big_drop_prompted_markdown_compliance',
    signal_type='BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE',
    formula='projected_cost = this_day_at_risk_value',
    description='Pure scorer using the current-day prompted-markdown compliance value at risk.',
)


def projected_cost(signal: dict, context: dict | None = None) -> float:  # noqa: ARG001
    return float(signal.get('this_day_at_risk_value') or 0.0)
