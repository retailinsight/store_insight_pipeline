from store_insight.pipeline.stages._2_score.scorers import osa_store_actionable


def test_projected_cost_is_weekly_store_controlled_lsv():
    signal = {
        'this_week_lsv': {
            'total': 500.0,
            'store_controlled': 225.0,
            'upstream': 250.0,
            'unknown': 25.0,
        }
    }
    assert osa_store_actionable.projected_cost(signal) == 225.0


def test_projected_cost_defaults_to_zero():
    assert osa_store_actionable.projected_cost({}) == 0.0
