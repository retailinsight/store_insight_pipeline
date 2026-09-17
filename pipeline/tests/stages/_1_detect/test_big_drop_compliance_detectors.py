from store_insight.pipeline.stages._1_detect.detectors.big_drop_expiry_date_compliance import (
    big_drop as expiry,
)
from store_insight.pipeline.stages._1_detect.detectors.big_drop_markdown_compliance import (
    big_drop as markdown,
)
from store_insight.pipeline.stages._1_detect.detectors.big_drop_prompted_markdown_compliance import (
    big_drop as prompted,
)


class _FakeDF:
    def __init__(self, rows):
        self.rows = rows

    def collect(self):
        return list(self.rows)


def test_markdown_big_drop_emits_daily_signal_with_workload():
    rows = [
        {'DATE': '2026-09-09', 'STORE_ID': 1, 'SITE_NAME': 'Store 1', 'DEPARTMENT_NAME': 'PRODUCE',
         'MARKDOWNS_DUE': 20, 'COMPLETED_ON_TIME': 18, 'AT_RISK_VALUE': 10.0},
        {'DATE': '2026-09-10', 'STORE_ID': 1, 'SITE_NAME': 'Store 1', 'DEPARTMENT_NAME': 'PRODUCE',
         'MARKDOWNS_DUE': 40, 'COMPLETED_ON_TIME': 20, 'AT_RISK_VALUE': 125.0},
        {'DATE': '2026-09-10', 'STORE_ID': 2, 'SITE_NAME': 'Store 2', 'DEPARTMENT_NAME': 'PRODUCE',
         'MARKDOWNS_DUE': 40, 'COMPLETED_ON_TIME': 36, 'AT_RISK_VALUE': 10.0},
    ]
    signals = markdown.detect(_FakeDF(rows), '2026-09-10')
    signal = signals[0]
    assert signal['signal_type'] == 'BIG_DROP_MARKDOWN_COMPLIANCE'
    assert signal['drop_pp'] == 40.0
    assert signal['this_day_at_risk_value'] == 125.0
    assert signal['workload']['volume_classification'] == 'INCREASING'


def test_expiry_big_drop_emits_daily_signal_with_workload():
    rows = [
        {'DATE': '2026-09-09', 'STORE_ID': 1, 'SITE_NAME': 'Store 1', 'DEPARTMENT_NAME': 'PRODUCE',
         'CHECKS_DUE': 20, 'CHECKS_COMPLETED': 18, 'AT_RISK_VALUE': 10.0},
        {'DATE': '2026-09-10', 'STORE_ID': 1, 'SITE_NAME': 'Store 1', 'DEPARTMENT_NAME': 'PRODUCE',
         'CHECKS_DUE': 40, 'CHECKS_COMPLETED': 20, 'AT_RISK_VALUE': 150.0},
        {'DATE': '2026-09-10', 'STORE_ID': 2, 'SITE_NAME': 'Store 2', 'DEPARTMENT_NAME': 'PRODUCE',
         'CHECKS_DUE': 40, 'CHECKS_COMPLETED': 36, 'AT_RISK_VALUE': 10.0},
    ]
    signals = expiry.detect(_FakeDF(rows), '2026-09-10')
    signal = signals[0]
    assert signal['signal_type'] == 'BIG_DROP_EXPIRY_DATE_COMPLIANCE'
    assert signal['drop_pp'] == 40.0
    assert signal['this_day_at_risk_value'] == 150.0
    assert signal['workload']['volume_classification'] == 'INCREASING'


def test_prompted_big_drop_emits_daily_signal_with_workload():
    rows = []
    for actioned in [True] * 9 + [False]:
        rows.append({'DATE': '2026-09-09', 'STORE_ID': 1, 'SITE_NAME': 'Store 1',
                     'DEPARTMENT_NAME': 'PRODUCE', 'ACTIONED_ON_TIME': actioned,
                     'RESPONSE_MINUTES': 20.0, 'AT_RISK_VALUE': 0.0})
    for actioned in [True] * 10 + [False] * 10:
        rows.append({'DATE': '2026-09-10', 'STORE_ID': 1, 'SITE_NAME': 'Store 1',
                     'DEPARTMENT_NAME': 'PRODUCE', 'ACTIONED_ON_TIME': actioned,
                     'RESPONSE_MINUTES': 40.0, 'AT_RISK_VALUE': 5.0})
    for actioned in [True] * 18 + [False] * 2:
        rows.append({'DATE': '2026-09-10', 'STORE_ID': 2, 'SITE_NAME': 'Store 2',
                     'DEPARTMENT_NAME': 'PRODUCE', 'ACTIONED_ON_TIME': actioned,
                     'RESPONSE_MINUTES': 10.0, 'AT_RISK_VALUE': 0.0})
    signals = prompted.detect(_FakeDF(rows), '2026-09-10')
    signal = signals[0]
    assert signal['signal_type'] == 'BIG_DROP_PROMPTED_MARKDOWN_COMPLIANCE'
    assert signal['drop_pp'] == 40.0
    assert signal['this_day_at_risk_value'] == 100.0
    assert signal['workload']['volume_classification'] == 'INCREASING'
