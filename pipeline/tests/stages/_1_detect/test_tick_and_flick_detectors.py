import pytest

from store_insight.pipeline.stages._1_detect.detectors.compliance import (
    tick_and_flick_vs_chain,
    tick_and_flick_wow,
)


class _Frame:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def collect(self):
        return self.rows


@pytest.mark.parametrize(
    ("detector", "trigger_type"),
    [
        (tick_and_flick_wow, "WOW"),
        (tick_and_flick_vs_chain, "VS_CHAIN"),
    ],
)
def test_split_detector_emits_compliance_signal_with_own_trigger(monkeypatch, detector, trigger_type):
    row = {
        "STORE_ID": 204,
        "SITE_NAME": "West Mersea",
        "THIS_WEEK_ALERTS_WORKED": 10,
        "THIS_WEEK_TF_COUNT": 5,
        "THIS_WEEK_TF_RATE": 0.5,
        "LAST_WEEK_ALERTS_WORKED": 10,
        "LAST_WEEK_TF_COUNT": 2,
        "LAST_WEEK_TF_RATE": 0.2,
        "TF_RATE_CHANGE": 0.3,
        "ABOVE_CHAIN_BY": 0.25,
    }
    monkeypatch.setattr(
        detector,
        "_joined_scores",
        lambda *_args, **_kwargs: (_Frame([row]), 0.25, 8),
    )

    signals = detector.detect(None, "2026-08-27", "2026-09-02", "2026-09-03", "2026-09-09")

    assert len(signals) == 1
    assert signals[0]["signal_type"] == "COMPLIANCE"
    assert signals[0]["trigger_types"] == [trigger_type]
    assert signals[0]["this_week_tf_rate"] == 50.0
