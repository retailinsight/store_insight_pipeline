from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='expiry_date_compliance',
    signal_type='EXPIRY_DATE_COMPLIANCE',
    formula='projected_cost = trailing_7d_at_risk_value',
    description='Pure scorer using current trailing-seven-day AT_RISK_VALUE.',
)


def projected_cost(signal: dict, context: dict | None = None) -> float:  # noqa: ARG001
    return float(signal.get('trailing_7d_at_risk_value') or 0.0)
