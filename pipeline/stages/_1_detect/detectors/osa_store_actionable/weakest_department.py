from __future__ import annotations

from snowflake.snowpark import functions as F
from store_insight.pipeline.pipeline._shared import (
    actionable_window_metrics as window_metrics,
)
from store_insight.pipeline.pipeline._shared import (
    attributed_values,
    quality_reasons,
    quality_values,
)
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_osa_store_actionable_signal

METADATA = DetectorInfo(
    name='WEAKEST_DEPARTMENT',
    problem='The store\'s weakest department by store-controlled OSA vs the chain, for engaged stores whose chain-relative and WoW detectors have nothing to fire on.',
    action='Prioritise the items and trading periods with recorded positive inventory and lost sales.',
    baseline='The chain department store-controlled OSA for the same week.',
    logic='Ranks the store\'s departments by OSA gap vs chain and fires once per store for the worst department within the store\'s top-N departments by store-controlled lost sales. Emits OSA_STORE_ACTIONABLE so card visuals, issue-key suppression and caps behave identically; a score multiplier keeps it behind genuine signals.',
    config_keys=['min_weakest_chain_gap', 'weakest_top_departments', 'min_weakest_lsv', 'min_actionable_positive_rows', 'max_actionable_unknown_row_pct'],
)


def detect(
    osa,
    this_week_start,
    this_week_end,
    section='ITEM_HIERARCHY_2',
    min_weakest_chain_gap=0.01,
    weakest_top_departments=5,
    min_weakest_lsv=0.0,
    min_actionable_positive_rows=10,
    max_actionable_unknown_row_pct=10.0,
    osa_full_chain=None,
):
    chain_osa = osa_full_chain if osa_full_chain is not None else osa
    store = window_metrics(osa, this_week_start, this_week_end, ['STORE_ID', section], 'STORE')
    chain = window_metrics(chain_osa, this_week_start, this_week_end, [section], 'CHAIN')
    rows = (
        store
        .filter(F.col('STORE_STORE_LSV') > min_weakest_lsv)
        .join(chain, on=section, how='left')
        .collect()
    )

    candidates = {}
    suppressed: dict[str, int] = {}
    for row in rows:
        store_quality = quality_values(row, 'STORE')
        chain_quality = quality_values(row, 'CHAIN')
        reasons = [
            *[f'store_{reason}' for reason in quality_reasons(store_quality, min_actionable_positive_rows, max_actionable_unknown_row_pct)],
            *[f'chain_{reason}' for reason in quality_reasons(chain_quality, min_actionable_positive_rows, max_actionable_unknown_row_pct)],
        ]
        if reasons:
            for reason in reasons:
                suppressed[reason] = suppressed.get(reason, 0) + 1
            continue

        gap = float(row['STORE_STORE_OSA'] or 0) - float(row['CHAIN_STORE_OSA'] or 0)
        store_id = int(row['STORE_ID'])
        lsv = float(row['STORE_STORE_LSV'] or 0)
        candidates.setdefault(store_id, []).append((gap, lsv, row))

    signals = []
    for store_id, depts in candidates.items():
        depts.sort(key=lambda d: d[1], reverse=True)
        eligible = [d for d in depts[:weakest_top_departments] if d[0] < -min_weakest_chain_gap]
        if not eligible:
            continue
        gap, lsv, row = min(eligible, key=lambda d: d[0])
        signals.append(make_osa_store_actionable_signal(
            store_id=store_id,
            department=row[section],
            trigger_types=['WEAKEST_DEPARTMENT'],
            this_week_osa=round(float(row['STORE_STORE_OSA'] or 0) * 100, 2),
            total_this_week_osa=round(float(row['STORE_TOTAL_OSA'] or 0) * 100, 2),
            chain_this_week_osa=round(float(row['CHAIN_STORE_OSA'] or 0) * 100, 2),
            total_chain_this_week_osa=round(float(row['CHAIN_TOTAL_OSA'] or 0) * 100, 2),
            chain_gap_pp=round(gap * 100, 2),
            this_week_lsv=attributed_values(row, 'STORE'),
            quality={'this_week': store_quality, 'chain_this_week': chain_quality},
        ))

    if suppressed:
        print(f'[osa_store_actionable.weakest_department] suppressed={suppressed}')
    return signals
