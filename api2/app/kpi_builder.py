"""
KPI Builder
===========
Reads a row from ``KPI_AVAILABILITY_SUMMARY`` and assembles the JSON response
matching ``KpisResponse`` in the frontend's ``shared/api.ts``.

Response shape:
    { "data": [overall_kpi, availability_kpi], "meta": { limit, offset, total } }
"""

import json

from snowflake.snowpark import Session
from snowflake.snowpark import functions as F

OUTPUT_TABLE = "SNOWFLAKE_LEARNING_DB.STORE_INSIGHT.KPI_AVAILABILITY_SUMMARY"


def _resolve_latest_row(
    session: Session,
    store_id: int | None,
    week_end_date: str | None,
):
    """
    Resolve the single KPI row to return.

    - If both ``store_id`` and ``week_end_date`` are given: exact lookup.
    - If only ``store_id``: latest ``ANALYSIS_DATE`` for that store.
    - If only ``week_end_date``: any store on that date (arbitrary).
    - If neither: latest ``ANALYSIS_DATE`` overall, arbitrary store on that date.
    """
    query = session.table(OUTPUT_TABLE)

    if store_id is not None:
        query = query.filter(F.col("STORE_ID") == store_id)

    if week_end_date is not None:
        query = query.filter(F.col("ANALYSIS_DATE") == week_end_date)
    else:
        # Pick the most recent ANALYSIS_DATE available in the remaining rows.
        query = query.order_by(F.col("ANALYSIS_DATE").desc())

    rows = (
        query.select(
            "STORE_ID",
            "ANALYSIS_DATE",
            "TW_OSA_PCT",
            "LW_OSA_PCT",
            "CLUSTER_OSA_PCT",
            "WOW_CHANGE_PP",
            "TREND_DIRECTION",
            "OVERALL_DETAILS_JSON",
            "AVAILABILITY_DETAILS_JSON",
        )
        .limit(1)
        .collect()
    )
    return rows[0] if rows else None


def get_kpis(
    session: Session,
    store_id: int | None = None,
    week_end_date: str | None = None,
) -> dict:
    """
    Fetch the pre-calculated KPI row and return the frontend JSON structure.

    Both parameters are optional — see ``_resolve_latest_row`` for how
    defaults are resolved.

    Raises ``ValueError`` if no row matches.
    """
    row = _resolve_latest_row(session, store_id, week_end_date)
    if row is None:
        raise ValueError(
            f"No KPI data found for store_id={store_id}, week_end_date={week_end_date}. "
            "Has the batch script been run?"
        )

    tw_osa       = float(row["TW_OSA_PCT"])
    cluster_osa  = float(row["CLUSTER_OSA_PCT"])
    wow_pp       = float(row["WOW_CHANGE_PP"])
    trend_dir    = str(row["TREND_DIRECTION"])

    overall_details      = json.loads(row["OVERALL_DETAILS_JSON"])
    availability_details = json.loads(row["AVAILABILITY_DETAILS_JSON"])

    overall_kpi = {
        "id":              "1",
        "name":            "Overall",
        "value":           f"{tw_osa:.1f}%",
        "trend_direction": trend_dir,
        "trend":           f"{wow_pp:+.1f}pp vs LW",
        "cluster_average": f"{cluster_osa:.1f}%",
        "details":         overall_details,
    }

    availability_kpi = {
        "id":              "2",
        "name":            "Availability",
        "value":           f"{tw_osa:.1f}%",
        "trend_direction": trend_dir,
        "trend":           f"{wow_pp:+.1f}pp vs LW",
        "cluster_average": f"{cluster_osa:.1f}%",
        "details":         availability_details,
    }

    data = [overall_kpi, availability_kpi]
    return {
        "data": data,
        "meta": {
            "limit":  len(data),
            "offset": 0,
            "total":  len(data),
        },
    }
