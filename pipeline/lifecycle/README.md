# Action lifecycle measurement

This module provides the building blocks for tracking whether generated alerts
lead to actions and whether those actions improve the underlying KPIs.

## Schema

Events are stored in `STORE_INSIGHT_DB.PUBLIC.ACTION_LIFECYCLE_EVENTS`:

| Column | Type | Notes |
|---|---|---|
| `EVENT_ID` | VARCHAR(36) PK | UUID |
| `EVENT_TIMESTAMP` | TIMESTAMP_NTZ | UTC time of the event |
| `ALERT_ID` | VARCHAR(16) | References `ALERTS_PIPELINE.ALERT_ID` |
| `RUN_ID` | VARCHAR(36) | Optional run linkage |
| `STORE_ID` | INTEGER | Denormalised for easy filtering |
| `EVENT_TYPE` | VARCHAR(32) | `seen`, `assigned`, `worked`, `closed`, `ignored` |
| `ACTOR` | VARCHAR(128) | User or system that emitted the event |
| `PAYLOAD` | VARIANT | Arbitrary JSON context |

Create the table once:

```python
from store_insight.pipeline.lifecycle import ensure_events_table

ensure_events_table(session)
```

## Recording events

```python
from store_insight.pipeline.lifecycle import record_event

record_event(
    session,
    alert_id="abc123",
    event_type="worked",
    run_id="...",
    store_id=508,
    actor="store.manager@example.com",
    payload={"resolution": "reordered"},
)
```

## Measurement

`measurement.py` contains SQL builders for:

- Funnel summary per run (`kpi_summary_sql`)
- Per-store action rates (`store_action_rate_sql`)
- A convenience view (`create_kpi_summary_view`)

```python
from store_insight.pipeline.lifecycle.measurement import create_kpi_summary_view

create_kpi_summary_view(session)
```

## Integration checklist

- [ ] UI/API emits `seen` when an alert is opened.
- [ ] UI/API emits `assigned` when ownership is recorded.
- [ ] UI/API emits `worked` when an action is taken.
- [ ] UI/API emits `closed` or `ignored` when the alert is resolved or dismissed.
- [ ] Combine funnel data with `ANALYSIS` source tables to measure KPI movement
      for actioned vs non-actioned stores.
