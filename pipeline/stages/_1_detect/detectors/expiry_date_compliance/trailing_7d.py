from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.expiry_date_compliance._core import (
    _chain_rate,
    _filtered_rows,
    _signal,
    _store_rates,
)

METADATA = DetectorInfo(
    name='TRAILING_7D',
    problem="A store's expiry-check completion rate deteriorated over the trailing seven days.",
    action='Review expiry-check workload and process with the store manager.',
    baseline='The same store during the preceding seven days.',
    logic='Weighted completion rate drop must meet the configured threshold and volume floor.',
    config_keys=['min_expiry_compliance_7d_drop', 'min_expiry_compliance_volume'],
)


def detect(expiry_date_compliance=None, last_week_start=None, last_week_end=None,
           this_week_start=None, this_week_end=None, min_expiry_compliance_7d_drop=0.05,
           min_expiry_compliance_volume=50, store_id=None):
    if expiry_date_compliance is None:
        return []
    rows = _filtered_rows(expiry_date_compliance, store_id)
    current = _store_rates(rows, this_week_start, this_week_end)
    previous = _store_rates(rows, last_week_start, last_week_end)
    current_chain = _chain_rate(current)
    previous_chain = _chain_rate(previous)
    chain_avg = sum(item['checks_due'] for item in current.values()) / len(current) if current else 0.0
    signals = []
    for sid, store in current.items():
        prior = previous.get(sid)
        if not prior or store['checks_due'] < min_expiry_compliance_volume:
            continue
        if prior['compliance_rate'] - store['compliance_rate'] >= min_expiry_compliance_7d_drop:
            signals.append(_signal(sid, store, prior, current_chain, previous_chain, chain_avg, 'TRAILING_7D'))
    print(f'[1_detect] EXPIRY_DATE_COMPLIANCE TRAILING_7D={len(signals)}')
    return signals
