from __future__ import annotations

import datetime

from store_insight.pipeline.email.daily_email import (
    ActionRow,
    ReminderRow,
    build_email,
    build_subject,
    cost_line,
    truncate,
)
from store_insight.pipeline.email.run_daily_email import run, uk_day_utc_bounds


def A(n):
    return ActionRow(f"ISSUE {n}", f"do thing {n}", f"£{n}.00 per week if not fixed.")
def R(t, n):
    return ReminderRow(f"ISSUE {n}", f"do thing {n}", f"£{n}.00 per week if not fixed.",
                             t, "Sam J", "check again")


class TestTruncate:
    def test_short_unchanged(self):
        assert truncate("short text") == "short text"

    def test_long_cuts_at_word_boundary(self):
        text = "word " * 60
        out = truncate(text)
        assert out.endswith("…")
        assert len(out) <= 201
        assert not out[:-1].endswith(" ")

    def test_none_and_empty(self):
        assert truncate(None) == "" and truncate("") == ""


class TestCost:
    def test_trims_trailing_stop(self):
        assert cost_line("£220.76 per week if not fixed.") == "£220.76 per week if not fixed"

    def test_empty(self):
        assert cost_line("") == "" and cost_line(None) == ""


class TestSubject:
    def test_both_sections(self):
        assert build_subject(2, 3, "Acle") == "StoreInsight: 2 new actions and 3 reminders today (Acle)"

    def test_actions_only(self):
        assert build_subject(8, 0, "Acle") == "StoreInsight: 8 new actions today (Acle)"

    def test_reminders_only(self):
        assert build_subject(0, 3, "Acle") == "StoreInsight: 3 reminders today (Acle)"

    def test_singular(self):
        assert build_subject(1, 1, "Acle") == "StoreInsight: 1 new action and 1 reminder today (Acle)"


class TestBuildEmail:
    def test_empty_both_skips(self):
        res = build_email(535, "Chesterwell", "s@x.co", [], [], "https://app")
        assert res.message is None
        assert res.skipped_reason == "skipped: nothing to report"

    def test_cap_five_plus_overflow(self):
        actions = [A(i) for i in range(8)]
        res = build_email(535, "Chesterwell", "s@x.co", actions, [], "https://app")
        assert res.message.subject.startswith("StoreInsight: 8 new actions today")
        assert "+ 3 more actions in StoreInsight" in res.message.text
        assert res.message.text.count("ISSUE") == 5

    def test_sections_hidden_when_empty(self):
        res = build_email(535, "Chesterwell", "s@x.co", [A(1)], [], "https://app")
        assert "REMINDERS SET FOR TODAY" not in res.message.text
        res2 = build_email(535, "Chesterwell", "s@x.co", [], [R("09:30", 1)], "https://app")
        assert "NEW ACTIONS TODAY" not in res2.message.text

    def test_cost_trimmed_and_setter_shown(self):
        res = build_email(535, "Chesterwell", "s@x.co", [A(1)], [R("09:30", 2)], "https://app")
        t = res.message.text
        assert "Cost: £1.00 per week if not fixed" in t and "£1.00 per week if not fixed." not in t
        assert 'Set by Sam J: "check again"' in t

    def test_html_contains_cta_and_disclaimer(self):
        res = build_email(535, "Chesterwell", "s@x.co", [A(1)], [], "https://app")
        assert "Open StoreInsight" in res.message.html
        assert "Replies to this address are not monitored" in res.message.html


class TestDispatchSafety:
    def test_disabled_never_queries_or_sends(self):
        def runner(*args):
            raise AssertionError("disabled job must not query or send")
        assert run(runner, "2026-11-04", {"enabled": False})[0].message is None

    def test_empty_store_logs_skip_without_send(self):
        writes = []
        def runner(sql, params):
            if "SELECT STORE_ID, STORE_NAME" in sql:
                return [{"STORE_ID": 445, "STORE_NAME": "Parkfields"}]
            if "INSERT INTO" in sql:
                writes.append(params)
            return []
        result = run(runner, "2026-11-04", {"enabled": True, "mailboxes": {445: {"email": "test@example.com"}}}, require_pipeline_ok=False)
        assert result[0].message is None
        assert len(writes) == 1
        assert writes[0]["reason"] == "skipped: nothing to report"

    def test_html_escaping_and_unicode(self):
        msg = build_email(1, "Test", "test@example.com", [ActionRow("<script>£ —</script>", "x", "£1")], [], "").message
        assert "<script>" not in msg.html
        assert "&lt;script&gt;£ —&lt;/script&gt;" in msg.html


class TestUkDayBounds:
    def test_dst_transition_days(self):
        spring = uk_day_utc_bounds(datetime.date(2026, 3, 29))
        autumn = uk_day_utc_bounds(datetime.date(2026, 10, 25))
        assert spring[1] - spring[0] == datetime.timedelta(hours=23)
        assert autumn[1] - autumn[0] == datetime.timedelta(hours=25)

    def test_gmt_and_bst(self):
        winter = uk_day_utc_bounds(datetime.date(2026, 1, 15))
        assert winter == (datetime.datetime(2026, 1, 15), datetime.datetime(2026, 1, 16))
        summer = uk_day_utc_bounds(datetime.date(2026, 7, 15))
        assert summer == (datetime.datetime(2026, 7, 14, 23), datetime.datetime(2026, 7, 15, 23))
