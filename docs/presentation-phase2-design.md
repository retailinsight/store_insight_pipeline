# Phase 2 presentation builders — design draft

**Status:** draft — awaiting Imran/Cornelious approval of widget shapes before code is written.
**Branch:** `feat/presentation-phase2-remaining-builders`

This document maps the five remaining signal types (which currently fall back to the old evidence renderer) to the existing `pipeline/presentation/models.py` widgets. All proposed widgets use the types that already exist:

- `stat`
- `matrix`
- `ranked_list`
- `bar_chart`
- `line_chart`

No new Pydantic model types are expected.

## Reusable patterns from existing builders

| Pattern | Source builder | How to reuse |
|---|---|---|
| Day/period matrix from a grid of rows | `osa_store_actionable.py` | Group rows by `day`/`date`, map `period_label` to `morning`/`afternoon`/`evening` keys. |
| Ranked list with barcode `secondary_label` | `osa_store_actionable.py` | Pick first `eans`/`upcs` value from `item_lsv_changes`. |
| Line chart with structured `{label, date}` categories | `compliance.py`, `binned_waste_*.py` | Build `ChartCategory` from the source date and day labels. |
| Two-series line chart | `binned_waste_*.py` | Add two `ChartSeries` objects to the same `LineChartWidget`. |
| `highlighted_index` on a bar chart | `binned_waste_spike.py` | Not needed for the remaining five types. |

## 1. PROMPTED_MARKDOWN_COMPLIANCE

Data source: `SIGNAL_JSON` scalars + `FACTS_JSON.daily_performance_last_7d[]`, `FACTS_JSON.worst_departments_top3[]`.

Proposed widgets:

1. `stat` — this week on-time compliance %.
2. `stat` — WoW change in percentage points.
3. `line_chart` — daily on-time compliance over 7 days (one series).
4. `ranked_list` — worst 3 departments by compliance %, `secondary_label` = `"actioned/prompts"`.

Example for store 204 (analysis date 2026-09-30):

```json
{
  "schema_version": 1,
  "widgets": [
    {
      "type": "stat",
      "id": "this_week_compliance_rate",
      "title": "On-time compliance",
      "value": 73.41,
      "format": "percentage"
    },
    {
      "type": "stat",
      "id": "wow_change_pp",
      "title": "Change vs last week",
      "value": -1.4,
      "format": "number"
    },
    {
      "type": "line_chart",
      "id": "daily_compliance",
      "title": "On-time compliance by day",
      "subtitle": "Last 7 days",
      "categories": [
        {"label": "Monday", "date": "2026-09-21"},
        {"label": "Tuesday", "date": "2026-09-22"},
        {"label": "Wednesday", "date": "2026-09-23"},
        {"label": "Thursday", "date": "2026-09-24"},
        {"label": "Friday", "date": "2026-09-25"},
        {"label": "Saturday", "date": "2026-09-26"},
        {"label": "Sunday", "date": "2026-09-27"}
      ],
      "series": [
        {
          "name": "On-time compliance %",
          "data": [65.17, 82.2, 44.49, 74.48, 75.33, 100.0, 90.95]
        }
      ],
      "format": "percentage"
    },
    {
      "type": "ranked_list",
      "id": "worst_departments",
      "title": "Worst departments",
      "subtitle": "By on-time compliance %",
      "items": [
        {"label": "MEAT PRODUCTS", "value": 20.0, "secondary_label": "1/5"},
        {"label": "BREAKFAST CEREALS", "value": 22.22, "secondary_label": "10/45"},
        {"label": "BEER/LAGER & CIDER", "value": 24.14, "secondary_label": "21/87"}
      ],
      "format": "percentage"
    }
  ]
}
```

Open question: should the `driver_assessment` block (likely driver, suggested check) be exposed as a widget, or is the existing issue/explanation text sufficient?

## 2. OSA_BIG_DROP

Data source: `SIGNAL_JSON` scalars + `FACTS_JSON.day_period_grid[]`, `FACTS_JSON.ppg_lsv[]`, `FACTS_JSON.item_lsv_changes[]`.

Proposed widgets:

1. `stat` — OSA % on the drop day (`this_week_osa`).
2. `stat` — OSA drop in pp (`wow_drift_pp`).
3. `matrix` — day/period lost sales value, currency format.
4. `ranked_list` — top PPGs by store-controlled lost sales value.
5. `ranked_list` — worst items by store-controlled lost sales value, with barcode `secondary_label`.

Example for store 213 (analysis date 2026-09-30):

```json
{
  "schema_version": 1,
  "widgets": [
    {
      "type": "stat",
      "id": "this_week_osa",
      "title": "OSA on drop day",
      "value": 89.14,
      "format": "percentage"
    },
    {
      "type": "stat",
      "id": "osa_drop_pp",
      "title": "OSA drop",
      "value": -10.86,
      "format": "number"
    },
    {
      "type": "matrix",
      "id": "day_period_grid",
      "title": "Lost sales by day and period",
      "columns": [
        {"key": "morning", "label": "Morning"},
        {"key": "afternoon", "label": "Afternoon"},
        {"key": "evening", "label": "Evening"}
      ],
      "rows": [
        {"label": "Monday", "date": "2026-09-21", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
        {"label": "Tuesday", "date": "2026-09-22", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
        {"label": "Wednesday", "date": "2026-09-23", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
        {"label": "Thursday", "date": "2026-09-24", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
        {"label": "Friday", "date": "2026-09-25", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
        {"label": "Saturday", "date": "2026-09-26", "values": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0}},
        {"label": "Sunday", "date": "2026-09-27", "values": {"morning": 27.16, "afternoon": 1.81, "evening": 0.0}}
      ],
      "format": "currency"
    },
    {
      "type": "ranked_list",
      "id": "ppg_lsv",
      "title": "Worst performing Sub Departments",
      "subtitle": "Store-controlled lost sales this week",
      "items": [
        {"label": "HAND ROLLING TOBACCO", "value": 28.97}
      ],
      "format": "currency"
    },
    {
      "type": "ranked_list",
      "id": "item_lsv_changes",
      "title": "Worst performing items",
      "subtitle": "Store-controlled lost sales this week",
      "items": [
        {"label": "GOLDEN VIRGINIA THE ORIGI", "value": 28.97, "secondary_label": "5000435010778"}
      ],
      "format": "currency"
    }
  ]
}
```

## 3. OSA_RECURRING_SLOT

Data source: `SIGNAL_JSON` scalars + `SIGNAL_JSON.repeat_item_details[]`, `FACTS_JSON.slot_history[]`.

Proposed widgets:

1. `stat` — total lost sales over the last 10 weeks.
2. `stat` — average weekly lost sales.
3. `line_chart` — weekly slot lost sales value history (currency).
4. `line_chart` — weekly slot OSA % history (percentage).
5. `ranked_list` — recurring items by lost sales value, `secondary_label` = item code.

Example for store 402, IN-STORE BAKERY, Saturday Morning (analysis date 2026-09-30):

```json
{
  "schema_version": 1,
  "widgets": [
    {
      "type": "stat",
      "id": "total_lsv",
      "title": "Total lost sales (10 weeks)",
      "value": 94.01,
      "format": "currency"
    },
    {
      "type": "stat",
      "id": "avg_weekly_lsv",
      "title": "Average weekly lost sales",
      "value": 16.79,
      "format": "currency"
    },
    {
      "type": "line_chart",
      "id": "slot_lsv_history",
      "title": "Slot lost sales history",
      "subtitle": "Last 10 weeks",
      "categories": [
        {"label": "2026-W35"},
        {"label": "2026-W36"},
        {"label": "2026-W37"},
        {"label": "2026-W38"},
        {"label": "2026-W39"}
      ],
      "series": [
        {"name": "Lost sales value", "data": [7.25, 13.0, 7.6, 56.85, 45.86]}
      ],
      "format": "currency"
    },
    {
      "type": "line_chart",
      "id": "slot_osa_history",
      "title": "Slot OSA history",
      "subtitle": "Last 10 weeks",
      "categories": [
        {"label": "2026-W35"},
        {"label": "2026-W36"},
        {"label": "2026-W37"},
        {"label": "2026-W38"},
        {"label": "2026-W39"}
      ],
      "series": [
        {"name": "OSA %", "data": [92.7, 82.6, 89.7, 15.1, 11.8]}
      ],
      "format": "percentage"
    },
    {
      "type": "ranked_list",
      "id": "recurring_items",
      "title": "Recurring items",
      "subtitle": "Lost sales over repeated weeks",
      "items": [
        {"label": "CP WHITE PARISIAN", "value": 35.17, "secondary_label": "29355"},
        {"label": "CP SAUSAGE ROLLS", "value": 31.05, "secondary_label": "29810"},
        {"label": "CP CHEESE TWIST", "value": 27.79, "secondary_label": "29348"}
      ],
      "format": "currency"
    }
  ]
}
```

Open question: do you want the LSV and OSA % histories as two separate line charts, or one combined chart? They have different units, so separate charts are safer.

## 4. MARKDOWN_OVERRIDE

Data source: `SIGNAL_JSON` scalars + `FACTS_JSON.override_dept_breakdown[]`.

Proposed widgets:

1. `stat` — this week override rate %.
2. `stat` — WoW change in pp.
3. `ranked_list` — departments by override rate %, `secondary_label` = `"overrides/total markdowns"`.

Example for store 404, INTERNATIONAL (analysis date 2026-09-30):

```json
{
  "schema_version": 1,
  "widgets": [
    {
      "type": "stat",
      "id": "this_week_override_rate",
      "title": "Override rate this week",
      "value": 5.67,
      "format": "percentage"
    },
    {
      "type": "stat",
      "id": "wow_change_pp",
      "title": "Change vs last week",
      "value": 5.67,
      "format": "number"
    },
    {
      "type": "ranked_list",
      "id": "override_departments",
      "title": "Departments by override rate",
      "items": [
        {"label": "CANNED FISH", "value": 50.0, "secondary_label": "2/4"},
        {"label": "CANNED & DRIED VEGETABLES", "value": 44.44, "secondary_label": "4/9"},
        {"label": "INTERNATIONAL", "value": 40.0, "secondary_label": "6/15"}
      ],
      "format": "percentage"
    }
  ]
}
```

## 5. MARKDOWN_SKU

Data source: `SIGNAL_JSON` scalars + `FACTS_JSON.sku_markdown_history[]`.

Proposed widgets:

1. `stat` — average markdown depth %.
2. `stat` — markdown request count over the lookback weeks.
3. `line_chart` — weekly markdown request count history.
4. `line_chart` — weekly average markdown % history.

Example for store 642, CP COD FLT SKIN/BONELESS (analysis date 2026-09-30):

```json
{
  "schema_version": 1,
  "widgets": [
    {
      "type": "stat",
      "id": "avg_markdown_pct",
      "title": "Average markdown depth",
      "value": 29.64,
      "format": "percentage"
    },
    {
      "type": "stat",
      "id": "markdown_request_count",
      "title": "Markdown requests (last 4 weeks)",
      "value": 14,
      "format": "number"
    },
    {
      "type": "line_chart",
      "id": "request_history",
      "title": "Weekly markdown requests",
      "categories": [
        {"label": "2026-08-24", "date": "2026-08-24"},
        {"label": "2026-08-31", "date": "2026-08-31"},
        {"label": "2026-09-07", "date": "2026-09-07"},
        {"label": "2026-09-14", "date": "2026-09-14"},
        {"label": "2026-09-21", "date": "2026-09-21"}
      ],
      "series": [
        {"name": "Requests", "data": [1, 3, 3, 4, 3]}
      ],
      "format": "number"
    },
    {
      "type": "line_chart",
      "id": "avg_markdown_history",
      "title": "Weekly average markdown depth",
      "categories": [
        {"label": "2026-08-24", "date": "2026-08-24"},
        {"label": "2026-08-31", "date": "2026-08-31"},
        {"label": "2026-09-07", "date": "2026-09-07"},
        {"label": "2026-09-14", "date": "2026-09-14"},
        {"label": "2026-09-21", "date": "2026-09-21"}
      ],
      "series": [
        {"name": "Avg markdown %", "data": [31.0, 30.0, 29.33, 29.5, 29.33]}
      ],
      "format": "percentage"
    }
  ]
}
```

Open question: do you want the request count and average markdown % as two separate line charts, or one combined chart? Again, they have different units.

## Confirmed decisions (Imran, 1 Oct)

1. `OSA_RECURRING_SLOT` and `MARKDOWN_SKU` use **two separate line charts** when the series have different units.
2. `ranked_list.format` matches the value semantics:
   - `currency` for lost sales / value;
   - `percentage` for compliance and override rates;
   - `number` for counts.
3. `secondary_label` is kept for supporting context: item codes, barcodes, action/override counts, etc.
4. `driver_assessment` stays in the existing issue/explanation text; no separate widget.
5. Widget types stay specific to the renderer (`matrix` for day/period grids, `line_chart` for series, etc.).

## Implementation notes

- All five builders can be added to `pipeline/presentation/builders/__init__.py` under `BUILDERS` and will be picked up automatically by `build_presentation()`.
- No new Pydantic model types are required.
- The builders should fail soft: if a source list is empty or missing, omit the widget rather than emit a zero-value placeholder.
- Empty presentation should result in `PRESENTATION_JSON = NULL` and the UI should continue to use the old fallback renderer.
