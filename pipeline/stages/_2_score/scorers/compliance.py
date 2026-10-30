"""
Scorer: COMPLIANCE
==================
projected_cost(signal, context) = SUM(LOST_SALES_VALUE of the items behind this
store's tick-and-flicked alerts this week)

A tick-and-flick event is a phantom resolution: the alert was closed without the
item being genuinely checked, so the underlying availability problem persists and
the store keeps losing sales that now look resolved on paper.

The cost is therefore the *actual* £ lost on the specific items that were
tick-and-flicked, not a whole-store average.  We take the feedback rows where
``TICK_AND_FLICK_FLAG`` is true and join each one to the OSA fact on
``(STORE_ID, ITEM_CODE, DATE)`` to pick up that item-day's ``LOST_SALES_VALUE``:

    tf_items      = DISTINCT (STORE_ID, ITEM_CODE, DATE) FROM feedback
                    WHERE TICK_AND_FLICK_FLAG = TRUE, this week
    projected_cost = SUM(osa.LOST_SALES_VALUE) over tf_items joined to osa

This attributes only the LSV genuinely tied to dismissed alerts, so a store that
tick-and-flicks high-LSV items scores higher than one dismissing items with no
lost sales — regardless of how many alerts it works overall.

Both the feedback and osa DataFrames are the same ones the detectors use, so no
new data source is introduced.

Public API
----------
    gather(signals, feedback, osa, this_week_start, this_week_end)
    -> dict keyed by store_id -> tick_and_flick_lsv (float)

    projected_cost(signal, context) -> float
"""

from snowflake.snowpark import functions as F
from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name        = 'compliance',
    signal_type = 'COMPLIANCE',
    formula     = 'SUM(COALESCE(osa.LOST_SALES_VALUE, 0)) for distinct tick-and-flicked (STORE_ID, ITEM_CODE, DATE) tuples',
    description = (
        '“Behind an alert” means the OSA fact for the same store, item, and '
        'alert-action date. For each flagged store, take current-week feedback '
        'rows where TICK_AND_FLICK_FLAG = TRUE; deduplicate to (store, item, '
        'date); left join OSA on those three fields; then sum LOST_SALES_VALUE. '
        'An alert with no matching OSA fact contributes £0. This is the observed '
        'alert-day availability loss for rapidly dismissed alerts, not a measured '
        'post-dismissal or future loss estimate.'
    ),
)


def gather(
    signals: list[dict],
    feedback,
    osa,
    this_week_start: str,
    this_week_end: str,
) -> dict:
    """
    Batch-compute the tick-and-flick LSV for each COMPLIANCE store.

    Takes the distinct (store, item, date) tuples that were tick-and-flicked
    this week and joins them to the OSA fact to sum the LOST_SALES_VALUE of
    those exact item-days.

    Parameters
    ----------
    signals         : list of COMPLIANCE signal dicts
    feedback        : Snowpark DataFrame — LSM_ALERT_FEEDBACK
                      (STORE_ID, ITEM_CODE, DATE, TICK_AND_FLICK_FLAG)
    osa             : Snowpark DataFrame — OSA source
                      (STORE_ID, ITEM_CODE, DATE, LOST_SALES_VALUE)
    this_week_start : date string (YYYY-MM-DD)
    this_week_end   : date string (YYYY-MM-DD)

    Returns
    -------
    dict keyed by store_id (int) -> tick_and_flick_lsv (float)
    """
    if not signals or feedback is None or osa is None:
        return {}

    store_ids = list({s['store_id'] for s in signals})

    tf_items = (
        feedback
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            (F.col('TICK_AND_FLICK_FLAG') == True) &
            F.col('STORE_ID').isin(store_ids)
        )
        .select('STORE_ID', 'ITEM_CODE', 'DATE')
        .distinct()
    )

    osa_lsv = (
        osa
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            F.col('STORE_ID').isin(store_ids)
        )
        .select(
            F.col('STORE_ID').alias('OSA_STORE_ID'),
            F.col('ITEM_CODE').alias('OSA_ITEM_CODE'),
            F.col('DATE').alias('OSA_DATE'),
            F.col('LOST_SALES_VALUE'),
        )
    )

    joined = (
        tf_items
        .join(
            osa_lsv,
            (tf_items['STORE_ID'] == osa_lsv['OSA_STORE_ID']) &
            (tf_items['ITEM_CODE'] == osa_lsv['OSA_ITEM_CODE']) &
            (tf_items['DATE'] == osa_lsv['OSA_DATE']),
            how='left',
        )
        .group_by('STORE_ID')
        .agg(F.sum('LOST_SALES_VALUE').alias('TF_LSV'))
    )

    return {
        int(r['STORE_ID']): float(r['TF_LSV'] or 0)
        for r in joined.collect()
    }


def projected_cost(signal: dict, context: dict | None = None) -> float:
    """
    Return projected weekly cost for a COMPLIANCE signal: the summed
    LOST_SALES_VALUE of the items this store tick-and-flicked this week.
    """
    return float((context or {}).get(signal['store_id'], 0.0))
