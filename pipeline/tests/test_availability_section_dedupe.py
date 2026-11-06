from __future__ import annotations

from store_insight.pipeline.stages._2_score.score import apply_availability_section_dedupe


def sig(store, dept, stype, score):
    return {'store_id': store, 'department': dept, 'signal_type': stype, 'score': score}


class TestAvailabilitySectionDedupe:
    def test_off_when_zero(self):
        signals = [sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 10),
                   sig(1, 'SOFT DRINKS', 'OSA_BIG_DROP', 20)]
        out = apply_availability_section_dedupe(signals, 0)
        assert len(out) == 2

    def test_actionable_beats_big_drop_same_dept(self):
        signals = [sig(1, 'SOFT DRINKS', 'OSA_BIG_DROP', 99),          # higher score loses
                   sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 5)]
        out = apply_availability_section_dedupe(signals, 1)
        assert len(out) == 1
        assert out[0]['signal_type'] == 'OSA_STORE_ACTIONABLE'

    def test_same_type_keeps_higher_score(self):
        signals = [sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 5),
                   sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 50)]
        out = apply_availability_section_dedupe(signals, 1)
        assert len(out) == 1
        assert out[0]['score'] == 50

    def test_different_departments_untouched(self):
        signals = [sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 5),
                   sig(1, 'BEER', 'OSA_BIG_DROP', 5)]
        assert len(apply_availability_section_dedupe(signals, 1)) == 2

    def test_different_stores_untouched(self):
        signals = [sig(1, 'SOFT DRINKS', 'OSA_BIG_DROP', 5),
                   sig(2, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 5)]
        assert len(apply_availability_section_dedupe(signals, 1)) == 2

    def test_non_availability_types_pass_through(self):
        signals = [sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 5),
                   sig(1, 'SOFT DRINKS', 'OSA_BIG_DROP', 5),
                   sig(1, 'SOFT DRINKS', 'OSA_RECURRING_SLOT', 5),
                   sig(1, 'COMPLIANCE', 'COMPLIANCE', 5)]
        out = apply_availability_section_dedupe(signals, 1)
        types = {s['signal_type'] for s in out}
        assert out[0]['signal_type'] == 'OSA_STORE_ACTIONABLE'
        assert 'COMPLIANCE' in types
        assert 'OSA_BIG_DROP' not in types
        assert 'OSA_RECURRING_SLOT' not in types

    def test_recurring_slot_loses_to_availability_same_dept(self):
        # Riverside feedback (6 Nov 2026): actionable + 2 slot cards for
        # TOBACCO read as repetition — actionable wins, slot cards drop.
        signals = [sig(1, 'TOBACCO', 'OSA_RECURRING_SLOT', 85),
                   sig(1, 'TOBACCO', 'OSA_STORE_ACTIONABLE', 607),
                   sig(1, 'TOBACCO', 'OSA_RECURRING_SLOT', 63)]
        out = apply_availability_section_dedupe(signals, 1)
        assert len(out) == 1
        assert out[0]['signal_type'] == 'OSA_STORE_ACTIONABLE'

    def test_recurring_slot_survives_without_availability(self):
        signals = [sig(1, 'TOBACCO', 'OSA_RECURRING_SLOT', 85),
                   sig(1, 'TOBACCO', 'OSA_RECURRING_SLOT', 63),
                   sig(1, 'COMPLIANCE', 'COMPLIANCE', 5)]
        out = apply_availability_section_dedupe(signals, 1)
        types = {s['signal_type'] for s in out}
        assert 'OSA_RECURRING_SLOT' in types and 'COMPLIANCE' in types
        assert sum(1 for s in out if s['signal_type'] == 'OSA_RECURRING_SLOT') == 1

    def test_dropped_not_returned(self):
        # dropped signals must not survive into the result (cap filter runs after)
        signals = [sig(1, 'SOFT DRINKS', 'OSA_BIG_DROP', 50),
                   sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 5)]
        out = apply_availability_section_dedupe(signals, 1)
        assert all(s['signal_type'] != 'OSA_BIG_DROP' for s in out)

    def test_max_two_allows_pair(self):
        signals = [sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 5),
                   sig(1, 'SOFT DRINKS', 'OSA_BIG_DROP', 5),
                   sig(1, 'SOFT DRINKS', 'OSA_STORE_ACTIONABLE', 9)]
        out = apply_availability_section_dedupe(signals, 2)
        assert len(out) == 2

    def test_missing_department_groups_none(self):
        # signals without a department group under None, still capped
        signals = [{'store_id': 1, 'signal_type': 'OSA_STORE_ACTIONABLE', 'score': 5},
                   {'store_id': 1, 'signal_type': 'OSA_BIG_DROP', 'score': 5}]
        assert len(apply_availability_section_dedupe(signals, 1)) == 1
