from __future__ import annotations

from snowflake.snowpark import functions as F

from store_insight.pipeline.pipeline._shared import (
    actionable_window_metrics as window_metrics,
)
from store_insight.pipeline.pipeline._shared import (
    attributed_values,
    quality_reasons,
    quality_values,
    subtract_attributed,
)
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo
from store_insight.pipeline.stages._1_detect.signals import make_osa_store_actionable_signal

METADATA = DetectorInfo(
    name='WOW',
    problem='Store-controlled availability deteriorated week-on-week.',
    action='Prioritise the items and trading periods with recorded positive inventory and lost sales.',
    baseline='The same store-department store-controlled OSA in the preceding week.',
    logic='Store-controlled OSA uses all sales volume plus positive-inventory lost-sales volume and fires on a configured weekly drop and store-controlled LSV gate.',
    config_keys=['min_actionable_wow_drop', 'min_actionable_lsv', 'min_actionable_positive_rows', 'max_actionable_unknown_row_pct'],
)


def detect(
    osa,
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    section='ITEM_HIERARCHY_2',
    min_actionable_wow_drop=0.01,
    min_actionable_lsv=200.0,
    min_actionable_positive_rows=10,
    max_actionable_unknown_row_pct=10.0,
):
    group_cols = ['STORE_ID', section]
    prior = window_metrics(osa, last_week_start, last_week_end, group_cols, 'PRIOR')
    latest = window_metrics(osa, this_week_start, this_week_end, group_cols, 'LATEST')
    rows = (
        prior
        .join(latest, on=group_cols, how='inner')
        .filter(F.col('LATEST_STORE_LSV') > min_actionable_lsv)
        .collect()
    )

    signals = []
    suppressed: dict[str, int] = {}
    for row in rows:
        prior_quality = quality_values(row, 'PRIOR')
        latest_quality = quality_values(row, 'LATEST')
        reasons = [
            *[f'prior_{reason}' for reason in quality_reasons(prior_quality, min_actionable_positive_rows, max_actionable_unknown_row_pct)],
            *[f'latest_{reason}' for reason in quality_reasons(latest_quality, min_actionable_positive_rows, max_actionable_unknown_row_pct)],
        ]
        if reasons:
            for reason in reasons:
                suppressed[reason] = suppressed.get(reason, 0) + 1
            continue

        drift = float(row['LATEST_STORE_OSA'] or 0) - float(row['PRIOR_STORE_OSA'] or 0)
        if drift >= -min_actionable_wow_drop:
            continue

        latest_lsv = attributed_values(row, 'LATEST')
        prior_lsv = attributed_values(row, 'PRIOR')
        signals.append(make_osa_store_actionable_signal(
            store_id=int(row['STORE_ID']),
            department=row[section],
            trigger_types=['WOW'],
            last_week_osa=round(float(row['PRIOR_STORE_OSA'] or 0) * 100, 2),
            this_week_osa=round(float(row['LATEST_STORE_OSA'] or 0) * 100, 2),
            total_last_week_osa=round(float(row['PRIOR_TOTAL_OSA'] or 0) * 100, 2),
            total_this_week_osa=round(float(row['LATEST_TOTAL_OSA'] or 0) * 100, 2),
            wow_drift_pp=round(drift * 100, 2),
            last_week_lsv=prior_lsv,
            this_week_lsv=latest_lsv,
            lsv_change=subtract_attributed(latest_lsv, prior_lsv),
            quality={'last_week': prior_quality, 'this_week': latest_quality},
        ))

    if suppressed:
        print(f'[osa_store_actionable.wow] suppressed={suppressed}')
    return signals
