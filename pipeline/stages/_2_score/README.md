# Stage 2: Scoring System Documentation

## 1. Overview

The scoring stage computes a **projected weekly £ cost** for each signal detected in Stage 1. This cost represents the financial impact of not addressing the issue, used for prioritisation.

**Key Design Principles:**
- **Scorers are independent** — they don't read `signal['facts']` (Stage 3) or narratives (Stage 4)
- **Two-phase execution** — batch DB queries first (`gather`), then per-signal scoring (`projected_cost`)
- **Pluggable architecture** — new scorers are added as self-contained modules
- **Signal-type dispatch** — each signal type maps to exactly one scorer via YAML config

---

## 2. Architecture Components

### 2.1 File Structure
```
pipeline/stages/_2_score/
├── config.py                    # ScorerInfo dataclass
├── protocols.py                 # ScorerModule Protocol
├── registry.py                  # Auto-discovery & YAML loading
├── score.py                     # Main orchestration (score_all)
├── composite.py                 # Composite scoring logic
├── signal_type_scorers.yaml     # Dispatch mapping
├── scorers/                     # Scorer implementations
│   ├── osa.py                   # Simple: direct field access
│   ├── waste.py                 # Simple: direct field access
│   ├── compliance.py            # With gather: needs DB query
│   ├── markdown_sku.py          # With gather: needs DB query
│   └── ...
└── dimensions/                  # Composite score dimensions
    ├── financial_severity.py
    ├── vs_control_benchmark.py
    └── ...
```

### 2.2 The ScorerModule Protocol

Every scorer module must satisfy this structural contract (`protocols.py`):

```python
class ScorerModule(Protocol):
    METADATA: ScorerInfo           # Static metadata
    
    def projected_cost(self, signal: dict, context: dict | None) -> float:
        """Return the projected weekly £ cost for a single signal."""
        ...
    
    # Optional: batch data gathering
    def gather(self, **kwargs) -> dict:
        """Run once per signal type, returns context for projected_cost."""
        ...
```

The `METADATA` attribute describes the scorer:
```python
@dataclass
class ScorerInfo:
    name: str           # Module name (e.g. 'compliance')
    signal_type: str    # Which signals it handles (e.g. 'COMPLIANCE')
    formula: str        # Human-readable formula
    description: str    # Plain English explanation
```

---

## 3. The Two-Phase Pattern

### 3.1 Phase 1: `gather()` — Batch Data Collection

**Purpose:** Run expensive DB queries once per signal type, not once per signal.

**When needed:** When the scorer requires data not already in the signal dict (e.g., aggregating from raw DataFrames).

**Signature:** `gather(**kwargs) -> dict`

**Example from `compliance.py`:**
```python
def gather(signals, feedback, osa, this_week_start, this_week_end) -> dict:
    """Sum the LSV of items behind each store's tick-and-flicked alerts."""
    store_ids = list({s['store_id'] for s in signals})

    tf_items = (
        feedback
        .filter(
            (F.col('DATE') >= this_week_start) &
            (F.col('DATE') <= this_week_end) &
            (F.col('TICK_AND_FLICK_FLAG') == True) &
            F.col('STORE_ID').isin(store_ids)
        )
        .select('STORE_ID', 'ITEM_CODE', 'DATE')
        .distinct()
    )
    # join tf_items to osa on (STORE_ID, ITEM_CODE, DATE), sum LOST_SALES_VALUE
    # -> {store_id: tick_and_flick_lsv}
```

**Key points:**
- Only receives kwargs it declares (via `inspect.signature` matching)
- Returns a dict (the `context`) passed to `projected_cost`
- Runs once per signal type, not per signal

### 3.2 Phase 2: `projected_cost()` — Per-Signal Calculation

**Purpose:** Compute the £ cost for a single signal.

**Signature:** `projected_cost(signal: dict, context: dict | None) -> float`

**Example from `osa.py` (simple — no gather needed):**
```python
def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost for an OSA signal."""
    return float(signal.get('this_week_lsv') or 0)
```

**Example from `compliance.py` (uses gather context):**
```python
def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Summed LSV of the items this store tick-and-flicked this week."""
    return float((context or {}).get(signal['store_id'], 0.0))
```

---

## 4. Registration System

### 4.1 YAML Configuration (`signal_type_scorers.yaml`)

The dispatch mapping is the single source of truth:

```yaml
OSA:
  name: osa
  description: projected_cost = this_week_lsv (direct £ — no DB query)

WASTE:
  name: waste
  description: projected_cost = this_week_waste_value (direct £ — no DB query)

COMPLIANCE:
  name: compliance
  description: projected_cost = SUM(osa.LOST_SALES_VALUE of items behind tick-and-flicked alerts)

MARKDOWN_SKU:
  name: markdown_sku
  description: projected_cost = (override_count / lookback_weeks) × avg_unit_markdown_value
```

**Rules:**
- Exactly one scorer per signal type
- `name` must match a Python module in `scorers/`
- Descriptions appear in pipeline docs and QC notebooks

### 4.2 Auto-Discovery (`registry.py`)

At import time, the registry:
1. Iterates all Python files in `scorers/`
2. Imports modules that expose `projected_cost`
3. Extracts `METADATA` from each
4. Builds `SIGNAL_TYPE_SCORERS` from the YAML mapping

**Exposed globals:**
- `ALL_SCORERS` — list of all scorer module objects
- `ALL_SCORER_INFO` — list of all `ScorerInfo` instances
- `SIGNAL_TYPE_SCORERS` — dict mapping `signal_type -> module`

---

## 5. Scoring Execution Flow

### 5.1 `score_all()` Orchestration (`score.py`)

```python
def score_all(signals, this_week_start, this_week_end,
              osa=None, markdown_log=None, markdown_sales=None,
              score_weights=None, scoring_cfg=None) -> None:
    """
    Stamps signal['score'] on every signal in-place.
    """
```

**Execution steps:**

1. **Group signals by type**
   ```python
   by_type: dict[str, list[dict]] = {}
   for sig in signals:
       by_type.setdefault(sig.get('signal_type', ''), []).append(sig)
   ```

2. **Run gather for each type** (if the scorer has a `gather` function)
   ```python
   for stype, scorer in _registry.SIGNAL_TYPE_SCORERS.items():
       type_signals = by_type.get(stype, [])
       if callable(getattr(scorer, 'gather', None)):
           gather_results[stype] = scorer.gather(
               **matching_kwargs(scorer.gather, {**all_kwargs, 'signals': type_signals})
           )
   ```

3. **Score each signal**
   ```python
   for signal in signals:
       scorer = _registry.SIGNAL_TYPE_SCORERS.get(signal['signal_type'])
       context = gather_results.get(signal['signal_type'])
       cost = scorer.projected_cost(signal, context)
       
       # Apply optional score weights
       cost *= (score_weights or {}).get(stype, 1.0)
       
       # Apply multipliers (if any registered)
       for m in _MULTIPLIERS:
           cost *= m(signal)
       
       signal['score'] = round(cost, 2)
   ```

### 5.2 Available Data Sources for gather()

The following kwargs are available for `gather()` functions to declare:

| Parameter | DataFrame | Description |
|-----------|-----------|-------------|
| `osa` | OSA fact table | Lost sales, availability data |
| `markdown_log` | Markdown log | Override decisions, timestamps |
| `markdown_sales` | Markdown sales | Markdown quantities/values |
| `this_week_start` | string | Start date (YYYY-MM-DD) |
| `this_week_end` | string | End date (YYYY-MM-DD) |
| `wmd_lookback` | string | 4 weeks before `this_week_end` |
| `signals` | list[dict] | Signals of this type being scored |

Only declare the parameters your `gather()` actually needs — the rest are filtered out via `matching_kwargs()`.

---

## 6. Composite Scoring

Beyond raw £ cost, signals can be scored using a **composite score** — a weighted sum of normalised dimensions in [0, 1].

### 6.1 Dimensions

| Dimension | Module | Description |
|-----------|--------|-------------|
| `financial_severity` | `financial_severity.py` | `min(projected_cost / ceiling, 1.0)` |
| `vs_control_benchmark` | `vs_control_benchmark.py` | How far store underperforms chain average |
| `vs_historical_benchmark` | `vs_historical_benchmark.py` | Week-on-week change magnitude |
| `thematic` | `thematic.py` | Business priority weighting |
| `historical_recency` | `historical_recency.py` | Recency bias for repeat issues |
| `special_cases` | `special_cases.py` | Manual overrides/hard-coding |

### 6.2 Configuration

Enable composite scoring by providing `composite_weights` in `scoring_cfg`:

```python
composite_weights = {
    'financial_severity': 0.5,
    'vs_control_benchmark': 0.2,
    'vs_historical_benchmark': 0.2,
    'thematic': 0.05,
    'historical_recency': 0.05,
    'special_cases': 0.0,
}

cost_ceilings = {'OSA': 5000, 'WASTE': 3000, ...}
benchmark_ceilings = {'OSA': 50, 'WASTE': 30, ...}  # percentage points
```

### 6.3 Calculation

```python
composite_score = sum(
    weight * dimension.score(signal, projected_cost, ceiling)
    for weight, dimension in dimensions.items()
)
```

---

## 7. Adding a New Scorer

### Step-by-Step Guide

**Step 1: Create the scorer module**

Create `scorers/my_alert.py`:

```python
"""
Scorer: MY_ALERT
================
projected_cost(signal, context) = ...

Explain what this score represents.
"""

from store_insight.pipeline.stages._2_score.config import ScorerInfo

METADATA = ScorerInfo(
    name='my_alert',
    signal_type='MY_ALERT',
    formula='this_week_value × multiplier',
    description='Explain what this scores and why.',
)

# Optional: only if you need DB data not in the signal
def gather(signals, osa, this_week_start, this_week_end) -> dict:
    """Batch query for additional data."""
    # ... query logic ...
    return {store_id: some_value}

def projected_cost(signal: dict, context: dict | None = None) -> float:
    """Return projected weekly cost."""
    this_week_value = float(signal.get('this_week_value') or 0)
    store_multiplier = (context or {}).get(signal['store_id'], 1.0)
    return this_week_value * store_multiplier
```

**Step 2: Register in YAML**

Add to `signal_type_scorers.yaml`:

```yaml
MY_ALERT:
  name: my_alert
  description: projected_cost = this_week_value × multiplier (queried from osa)
```

**Step 3: No other changes needed**

The registry auto-discovers the module. The pipeline will:
1. Call `gather()` once for all MY_ALERT signals
2. Call `projected_cost(signal, context)` for each signal
3. Stamp `signal['score']`

---

## 8. Example Patterns

### 8.1 Simple Scorer (no DB query)

**Use when:** The signal dict already contains all needed data.

```python
# osa.py
METADATA = ScorerInfo(...)
# No gather() function needed

def projected_cost(signal, context=None) -> float:
    return float(signal.get('this_week_lsv') or 0)
```

### 8.2 Scorer with Batch Query

**Use when:** Need to aggregate from raw DataFrames.

```python
# markdown_sku.py
def gather(signals, markdown_sales, wmd_lookback, this_week_end) -> dict:
    """Compute avg_unit_markdown_value per (store, item)."""
    store_ids = list({s['store_id'] for s in signals})
    item_ids = [str(s['item_id']) for s in signals]
    
    result = (
        markdown_sales
        .filter(
            (F.col('DATE') >= wmd_lookback) &
            F.col('STORE_ID').isin(store_ids) &
            F.col('UPC').cast('string').isin(item_ids)
        )
        .group_by('STORE_ID', 'UPC')
        .agg(
            F.sum('MARKDOWN_VALUE').alias('TOTAL_VALUE'),
            F.sum('MARKDOWN_QUANTITY').alias('TOTAL_QTY'),
        )
        .with_column('AVG_UNIT', F.col('TOTAL_VALUE') / F.col('TOTAL_QTY'))
    )
    
    return {
        (int(r['STORE_ID']), int(r['UPC'])): float(r['AVG_UNIT'] or 0)
        for r in result.collect()
    }

def projected_cost(signal, context=None) -> float:
    override_count = float(signal.get('override_count') or 0)
    lookback_weeks = float(signal.get('lookback_weeks') or 1)
    key = (signal['store_id'], signal['item_id'])
    avg_unit_value = (context or {}).get(key, 0.0)
    return (override_count / lookback_weeks) * avg_unit_value
```

---

## 9. Key Takeaways

1. **Scorers are pure functions** — they take signal + context, return a float
2. **Use `gather()` for DB queries** — run once per signal type, not per signal
3. **YAML drives dispatch** — `signal_type_scorers.yaml` is the single source of truth
4. **Registration is automatic** — drop a file in `scorers/`, add YAML entry, done
5. **Composite scoring is optional** — raw £ cost is the default; enable via config
6. **Scorers are independent** — they only read Stage-1 signal fields and raw DataFrames
