from store_insight.pipeline.pipeline._shared import (
    attributed_lsv,
    project_attributed,
    quality_is_valid,
    quality_reasons,
    subtract_attributed,
)


def test_inventory_attribution_buckets_reconcile():
    assert attributed_lsv(2, 10) == {
        'total': 10.0, 'store_controlled': 10.0, 'upstream': 0.0, 'unknown': 0.0,
    }
    assert attributed_lsv(0, 10)['upstream'] == 10.0
    assert attributed_lsv(-1, 10)['upstream'] == 10.0
    assert attributed_lsv(None, 10)['unknown'] == 10.0


def test_attributed_subtraction_and_projection():
    latest = {'total': 20, 'store_controlled': 10, 'upstream': 8, 'unknown': 2}
    prior = {'total': 15, 'store_controlled': 4, 'upstream': 10, 'unknown': 1}
    assert subtract_attributed(latest, prior) == {
        'total': 5.0, 'store_controlled': 6.0, 'upstream': -2.0, 'unknown': 1.0,
    }
    assert project_attributed(latest, 4)['store_controlled'] == 40.0


def test_quality_boundaries_are_inclusive():
    valid = {
        'positive_inventory_rows': 10,
        'unknown_inventory_row_pct': 10.0,
    }
    assert quality_is_valid(valid, 10, 10.0)
    assert quality_reasons(valid, 10, 10.0) == []
    assert quality_reasons({**valid, 'positive_inventory_rows': 9}, 10, 10.0) == [
        'insufficient_positive_inventory_rows'
    ]
    assert quality_reasons({**valid, 'unknown_inventory_row_pct': 10.01}, 10, 10.0) == [
        'excessive_unknown_inventory_rows'
    ]
