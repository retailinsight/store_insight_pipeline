"""
Stage 5 — Outcome Measurement
==============================
Measures whether Store Insight insights that received a Commitment were
subsequently resolved.

A Commitment is eligible for measurement when the current pipeline
``analysis_date`` is at least 7 days after the committed card's ``RUN_DATE``.
This guarantees one full week of recovery time regardless of the day the card
was generated.

Resolution is determined by absence: if no alert card was emitted for
``(STORE_ID, SIGNAL_TYPE, SECTION)`` in the current run, the signal is
considered resolved.

Estimated Value Recovered is the ``projected_cost`` from the original card's
``SIGNAL_JSON`` if the signal was resolved; NULL otherwise.

Public API
----------
    measure_outcomes(session, current_run_date, cfg=None) -> list[dict]
"""

import datetime
import json


def _parse_date(d) -> datetime.date:
    if isinstance(d, datetime.date):
        return d
    return datetime.date.fromisoformat(str(d))


def _feedback_table(cfg) -> str:
    if cfg and hasattr(cfg, 'tables') and hasattr(cfg.tables, 'insight_feedback'):
        return cfg.tables.insight_feedback
    return 'STORE_INSIGHT_FEEDBACK'


def _outcomes_table(cfg) -> str:
    if cfg and hasattr(cfg, 'output') and hasattr(cfg.output, 'outcomes'):
        return cfg.output.outcomes
    return 'STORE_INSIGHT_OUTCOMES'


def _alerts_table(cfg) -> str:
    if cfg and hasattr(cfg, 'output') and hasattr(cfg.output, 'alerts'):
        return cfg.output.alerts
    return 'ALERTS_PIPELINE'


def measure_outcomes(session, current_run_date: str, cfg=None) -> list[dict]:
    """
    Measure outcomes for all eligible, unmeasured Commitments.

    Parameters
    ----------
    session          : Snowpark Session
    current_run_date : str — YYYY-MM-DD (today's analysis_date)
    cfg              : optional PipelineConfig

    Returns
    -------
    list of outcome dicts:
        alert_id, store_id, signal_type, section, card_run_date,
        outcome_run_date, signal_resolved, estimated_value_recovered
    """
    current_date = _parse_date(current_run_date)
    eligibility_cutoff = str(current_date - datetime.timedelta(days=7))

    feedback_tbl = _feedback_table(cfg)
    outcomes_tbl = _outcomes_table(cfg)
    alerts_tbl   = _alerts_table(cfg)

    try:
        feedback_df = session.table(feedback_tbl)
    except Exception:
        print(f'[outcomes] {feedback_tbl} not found — skipping outcome measurement.')
        return []

    try:
        outcomes_df = session.table(outcomes_tbl)
        existing_ids = {
            r['ALERT_ID']
            for r in outcomes_df.select('ALERT_ID').collect()
        }
    except Exception:
        existing_ids = set()

    try:
        all_feedback_rows = feedback_df.collect()
    except Exception as exc:
        print(f'[outcomes] Could not query {feedback_tbl}: {exc}')
        return []

    eligibility_date = datetime.date.fromisoformat(eligibility_cutoff)

    pending = [
        r.as_dict() for r in all_feedback_rows
        if r['ALERT_ID'] not in existing_ids
        and _parse_date(r['CARD_RUN_DATE']) <= eligibility_date
    ]

    if not pending:
        print('[outcomes] No eligible unmeasured Commitments.')
        return []

    pending_ids = {p['ALERT_ID'] for p in pending}

    try:
        all_alert_rows = [r.as_dict() for r in session.table(alerts_tbl).collect()]
    except Exception:
        all_alert_rows = []

    today_set = {
        (int(r['STORE_ID']), r['SIGNAL_TYPE'], r['SECTION'])
        for r in all_alert_rows
        if r.get('RUN_DATE') == current_run_date
        and r.get('ALERT_ID') not in pending_ids
    }

    original_cards = {
        r['ALERT_ID']: r
        for r in all_alert_rows
        if r.get('ALERT_ID') in pending_ids
    }

    outcomes = []
    for commitment in pending:
        alert_id    = commitment['ALERT_ID']
        store_id    = int(commitment['STORE_ID'])
        signal_type = commitment['SIGNAL_TYPE']
        section     = commitment.get('SECTION')

        lookup_key = (store_id, signal_type, section)
        resolved   = lookup_key not in today_set

        projected_cost = None
        if resolved:
            orig = original_cards.get(alert_id, {})
            signal_json_raw = orig.get('SIGNAL_JSON')
            if signal_json_raw:
                try:
                    signal_json = json.loads(signal_json_raw)
                    projected_cost = signal_json.get('projected_cost')
                except (json.JSONDecodeError, TypeError):
                    pass

        outcomes.append({
            'alert_id':                  alert_id,
            'store_id':                  store_id,
            'signal_type':               signal_type,
            'section':                   section,
            'card_run_date':             str(commitment['CARD_RUN_DATE']),
            'outcome_run_date':          current_run_date,
            'signal_resolved':           resolved,
            'estimated_value_recovered': projected_cost,
        })

    print(f'[outcomes] {len(outcomes)} outcomes measured.')
    return outcomes
