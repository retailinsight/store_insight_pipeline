"""
Tests for ALERT_ID on alert cards.

Behaviors tested:
  1. _build_card() includes an alert_id key
  2. Same (run_date, store_id, alert_type, section) → same alert_id
  3. Different natural keys → different alert_id
  4. section=None and section='' → same alert_id
"""

from store_insight.pipeline.pipeline.pipeline import _build_card

_NARRATIVE = {
    'issue':              'Test issue',
    'explanation':        'Test explanation',
    'cost_if_not_fixed':  '£100/week',
    'recommended_action': 'Fix it',
}

def _sig(store_id=1, signal_type='OSA', trigger_types=None, department=None):
    return {
        'store_id':     store_id,
        'signal_type':  signal_type,
        'trigger_types': trigger_types or ['WOW'],
        'department':   department,
    }


def _recurring_slot_sig(store_id=1, department='CHILLED', dow=2, period_id=1):
    return {
        'store_id':      store_id,
        'signal_type':   'OSA_RECURRING_SLOT',
        'trigger_types': ['RECURRING_SLOT'],
        'department':    department,
        'dow':           dow,
        'period_id':     period_id,
    }


def test_build_card_includes_alert_id():
    card = _build_card(_sig(), _NARRATIVE, sort_value=0.5)
    assert 'alert_id' in card


def test_same_natural_key_produces_same_alert_id():
    sig = _sig(store_id=42, signal_type='OSA', department='Produce')
    card_a = _build_card(sig, _NARRATIVE, sort_value=0.5)
    card_b = _build_card(sig, _NARRATIVE, sort_value=0.9)
    assert card_a['alert_id'] == card_b['alert_id']


def test_different_natural_keys_produce_different_alert_ids():
    card_a = _build_card(_sig(store_id=1,  signal_type='OSA'),   _NARRATIVE, sort_value=0.5)
    card_b = _build_card(_sig(store_id=2,  signal_type='OSA'),   _NARRATIVE, sort_value=0.5)
    card_c = _build_card(_sig(store_id=1,  signal_type='WASTE'),  _NARRATIVE, sort_value=0.5)
    assert card_a['alert_id'] != card_b['alert_id']
    assert card_a['alert_id'] != card_c['alert_id']


def test_section_none_and_empty_string_produce_same_alert_id():
    card_none  = _build_card(_sig(department=None), _NARRATIVE, sort_value=0.5)
    card_empty = _build_card(_sig(department=''),   _NARRATIVE, sort_value=0.5)
    assert card_none['alert_id'] == card_empty['alert_id']


def test_recurring_slot_different_dow_period_produce_different_alert_ids():
    # Regression: a single store+department can have multiple distinct
    # OSA_RECURRING_SLOT alerts (one per day-of-week + reporting-period
    # slot). These must not collide onto the same ALERT_ID, or the queue
    # stage will treat unrelated alerts as duplicates of one another.
    card_a = _build_card(_recurring_slot_sig(dow=2, period_id=1), _NARRATIVE, sort_value=0.5)
    card_b = _build_card(_recurring_slot_sig(dow=4, period_id=3), _NARRATIVE, sort_value=0.5)
    assert card_a['alert_id'] != card_b['alert_id']


def test_recurring_slot_same_dow_period_produces_same_alert_id():
    card_a = _build_card(_recurring_slot_sig(dow=2, period_id=1), _NARRATIVE, sort_value=0.5)
    card_b = _build_card(_recurring_slot_sig(dow=2, period_id=1), _NARRATIVE, sort_value=0.9)
    assert card_a['alert_id'] == card_b['alert_id']
