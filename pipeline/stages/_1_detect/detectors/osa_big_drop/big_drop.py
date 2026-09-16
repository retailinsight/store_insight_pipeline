from __future__ import annotations

import datetime

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
from store_insight.pipeline.stages._1_detect.signals import make_osa_big_drop_signal

METADATA = DetectorInfo(
    name='BIG_DROP',
    problem='Store-controlled availability dropped sharply from one day to the next.',
    action='Prioritise the items and trading periods with recorded positive inventory and lost sales.',
    baseline='The same store-department store-controlled OSA on the most recent preceding sales day in the data.',
    logic='Store-controlled OSA uses all sales volume plus positive-inventory lost-sales volume and fires when the day-on-day drop exceeds 5 percentage points and the quality gates (5 positive-inventory rows and <10% unknown-inventory rows) are met. The preceding day is the latest sales day before the analysis date, not the strict calendar yesterday.',
    config_keys=['min_actionable_big_drop', 'min_osa_big_drop_lsv', 'min_big_drop_positive_rows', 'max_actionable_unknown_row_pct'],
)


def detect(
    osa,
    this_week_end,
    section='ITEM_HIERARCHY_2',
    min_actionable_big_drop=0.05,
    min_osa_big_drop_lsv=50.0,
    min_big_drop_positive_rows=5,
    max_actionable_unknown_row_pct=10.0,
):
    requested_date = str(this_week_end)
    available_dates = (
        osa
        .filter(F.col('DATE') <= requested_date)
        .select('DATE')
        .distinct()
        .sort(F.col('DATE').desc())
        .limit(2)
        .collect()
    )
    if len(available_dates) < 2:
        print(f'[osa_big_drop.big_drop] fewer than two sales days available by {requested_date}')
        return []
    latest_date = str(available_dates[0]['DATE']).split()[0]
    prior_date = str(available_dates[1]['DATE']).split()[0]
    latest_day = datetime.date.fromisoformat(latest_date).strftime('%A')
    prior_day = datetime.date.fromisoformat(prior_date).strftime('%A')
    print(f'[osa_big_drop.big_drop] comparing {latest_date} vs {prior_date}')

    group_cols = ['STORE_ID', section]
    prior = window_metrics(osa, prior_date, prior_date, group_cols, 'PRIOR')
    latest = window_metrics(osa, latest_date, latest_date, group_cols, 'LATEST')
    rows = (
        prior
        .join(latest, on=group_cols, how='inner')
        .collect()
    )

    signals = []
    suppressed: dict[str, int] = {}
    for row in rows:
        prior_quality = quality_values(row, 'PRIOR')
        latest_quality = quality_values(row, 'LATEST')
        reasons = [
            *[f'prior_{reason}' for reason in quality_reasons(prior_quality, min_big_drop_positive_rows, max_actionable_unknown_row_pct)],
            *[f'latest_{reason}' for reason in quality_reasons(latest_quality, min_big_drop_positive_rows, max_actionable_unknown_row_pct)],
        ]
        if reasons:
            for reason in reasons:
                suppressed[reason] = suppressed.get(reason, 0) + 1
            continue

        drift = float(row['LATEST_STORE_OSA'] or 0) - float(row['PRIOR_STORE_OSA'] or 0)
        if drift >= -min_actionable_big_drop:
            suppressed['drop_below_threshold'] = suppressed.get('drop_below_threshold', 0) + 1
            continue

        latest_lsv = attributed_values(row, 'LATEST')
        if (latest_lsv.get('store_controlled') or 0) < min_osa_big_drop_lsv:
            suppressed['lsv_below_threshold'] = suppressed.get('lsv_below_threshold', 0) + 1
            continue

        prior_lsv = attributed_values(row, 'PRIOR')
        signals.append(make_osa_big_drop_signal(
            store_id=int(row['STORE_ID']),
            department=row[section],
            trigger_types=['BIG_DROP'],
            last_week_osa=round(float(row['PRIOR_STORE_OSA'] or 0) * 100, 2),
            this_week_osa=round(float(row['LATEST_STORE_OSA'] or 0) * 100, 2),
            total_last_week_osa=round(float(row['PRIOR_TOTAL_OSA'] or 0) * 100, 2),
            total_this_week_osa=round(float(row['LATEST_TOTAL_OSA'] or 0) * 100, 2),
            wow_drift_pp=round(drift * 100, 2),
            last_week_lsv=prior_lsv,
            this_week_lsv=latest_lsv,
            lsv_change=subtract_attributed(latest_lsv, prior_lsv),
            latest_day=latest_day,
            prior_day=prior_day,
            latest_date=latest_date,
            prior_date=prior_date,
            quality={'previous_day': prior_quality, 'current_day': latest_quality},
        ))

    print(f'[osa_big_drop.big_drop] total_pairs={len(rows)} emitted={len(signals)} suppressed={suppressed}')
    return signals
