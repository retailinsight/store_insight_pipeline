from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.detectors.expiry_date_compliance._core import (
    _chain_rate,
    _filtered_rows,
    _signal,
    _store_rates,
)

METADATA = DetectorInfo(
    name='VS_CHAIN',
    problem="A store's trailing expiry-check completion rate is below chain.",
    action='Review the store expiry-check process against peers.',
    baseline='Weighted chain completion rate for the same trailing seven days.',
    logic='Weighted chain gap must meet the configured threshold and volume floor.',
    config_keys=['min_expiry_compliance_chain_gap', 'min_expiry_compliance_volume'],
)


def detect(expiry_date_compliance=None, this_week_start=None, this_week_end=None,
           last_week_start=None, last_week_end=None, min_expiry_compliance_chain_gap=0.05,
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
        if current_chain is None or store['checks_due'] < min_expiry_compliance_volume:
            continue
        if current_chain - store['compliance_rate'] >= min_expiry_compliance_chain_gap:
            signals.append(_signal(sid, store, previous.get(sid), current_chain, previous_chain, chain_avg, 'VS_CHAIN'))
    print(f'[1_detect] EXPIRY_DATE_COMPLIANCE VS_CHAIN={len(signals)}')
    return signals
