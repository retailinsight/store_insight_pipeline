"""Tests for the detection-time ranging filter (Trello: ranging/delisting).

The filter must:
- drop OSA rows whose (STORE_ID, ITEM_CODE) is absent from the latest
  ranging snapshot;
- keep ranged rows, including items absent from a different store;
- fail open (run unfiltered) when the ranging feed is missing, empty or
  stale, so a broken feed cannot silently drop genuine gaps.
"""

import datetime
import types

import pytest
from snowflake.snowpark import Session

from store_insight.pipeline.pipeline.run_batch import (
    RANGING_MAX_STALENESS_DAYS,
    filter_not_ranged,
    load_ranging,
)


@pytest.fixture(scope="module")
def local_session():
    session = Session.builder.config("local_testing", True).create()
    yield session
    session.close()


def _osa(local_session, rows):
    return local_session.create_dataframe(
        rows,
        schema=[
            "STORE_ID",
            "ITEM_CODE",
            "DATE",
            "ITEM_HIERARCHY_2",
            "ACTUAL_SALES_VOLUME",
            "LOST_SALES_VOLUME",
            "INVENTORY_QTY",
        ],
    )


def _ranging(local_session, rows):
    return local_session.create_dataframe(rows, schema=["STORE_ID", "ITEM_CODE"])


def test_filter_not_ranged_drops_unranged_items(local_session):
    osa = _osa(
        local_session,
        [
            (204, "A", "2026-10-25", "GROCERY", 10.0, 1.0, 5.0),
            (204, "DELISTED", "2026-10-25", "GROCERY", 10.0, 5.0, 5.0),
            (239, "A", "2026-10-25", "GROCERY", 10.0, 1.0, 5.0),
        ],
    )
    ranging = _ranging(local_session, [(204, "A"), (239, "A")])

    kept = {r["ITEM_CODE"] for r in filter_not_ranged(osa, ranging).collect()}
    assert kept == {"A"}


def test_filter_not_ranged_is_per_store(local_session):
    """Item ranged at store 239 but not 204 is dropped only for 204."""
    osa = _osa(
        local_session,
        [
            (204, "X", "2026-10-25", "GROCERY", 10.0, 1.0, 5.0),
            (239, "X", "2026-10-25", "GROCERY", 10.0, 1.0, 5.0),
        ],
    )
    ranging = _ranging(local_session, [(239, "X")])

    kept = {(r["STORE_ID"], r["ITEM_CODE"]) for r in filter_not_ranged(osa, ranging).collect()}
    assert kept == {(239, "X")}


def _cfg(table="STORE_INSIGHT_DB.PUBLIC.RANGING_V1"):
    return types.SimpleNamespace(tables=types.SimpleNamespace(ranging=table))


class _FakeTable:
    """Minimal Snowpark-ish frame for load_ranging's select/agg/select calls."""

    def __init__(self, max_ts=None, raise_on_table=False):
        self._max_ts = max_ts

    def select(self, *a, **k):
        return self

    def distinct(self):
        return self

    def cache_result(self):
        return self

    def agg(self, *a, **k):
        fake = types.SimpleNamespace()
        fake.collect = lambda: [(self._max_ts,)]
        return fake


class _FakeSession:
    def __init__(self, table=None, raises=False):
        self._table = table
        self._raises = raises

    def table(self, _name):
        if self._raises:
            raise RuntimeError("no such object")
        return self._table


def test_load_ranging_returns_keys_when_fresh():
    fresh = datetime.date.today() - datetime.timedelta(days=1)
    session = _FakeSession(table=_FakeTable(max_ts=fresh))
    out = load_ranging(session, str(datetime.date.today()), cfg=_cfg())
    assert out is session._table  # the same cached frame object is returned


def test_load_ranging_fails_open_on_stale_file():
    stale = datetime.date.today() - datetime.timedelta(days=RANGING_MAX_STALENESS_DAYS + 2)
    session = _FakeSession(table=_FakeTable(max_ts=stale))
    assert load_ranging(session, str(datetime.date.today()), cfg=_cfg()) is None


def test_load_ranging_fails_open_on_missing_table():
    session = _FakeSession(raises=True)
    assert load_ranging(session, str(datetime.date.today()), cfg=_cfg()) is None


def test_load_ranging_fails_open_on_empty_table():
    session = _FakeSession(table=_FakeTable(max_ts=None))
    assert load_ranging(session, str(datetime.date.today()), cfg=_cfg()) is None


def test_load_ranging_no_config_no_filter():
    session = _FakeSession(table=_FakeTable(max_ts=datetime.date.today()))
    cfg = types.SimpleNamespace(tables=types.SimpleNamespace(ranging=None))
    assert load_ranging(session, str(datetime.date.today()), cfg=cfg) is None


def test_load_ranging_skipped_without_capability():
    session = _FakeSession(table=_FakeTable(max_ts=datetime.date.today()))
    out = load_ranging(session, str(datetime.date.today()), cfg=_cfg(), capabilities={"osa"})
    assert out is None
