# Stage 1 — Detection (`_1_detect`)

Runs all registered detectors against the OSA and feedback data, merges
signals that share the same logical key, and returns a flat list of signal
dicts for the rest of the pipeline.

---

## Architecture

```
_1_detect/
├── detect.py       Public entry point — detect_signals()
├── registry.py     Auto-discovers detectors/ and exposes ALL_DETECTORS / ALL_DETECTOR_INFO
├── config.py       DetectorConfig (thresholds) + DetectorInfo (metadata schema)
├── signals.py      Signal factories — make_osa_signal(), make_compliance_signal()
└── detectors/
    ├── osa_wow.py
    ├── osa_vs_chain.py
    ├── osa_repeat.py
    └── tick_and_flick.py
```

### Flow

```
detect_signals()
    └── for each detector in registry.ALL_DETECTORS
            └── detector.detect(**relevant_kwargs)  →  list[signal]
    └── _merge_signals(all_signals)  →  one signal per merge_key
    └── return flat list
```

---

## Signal Types

Every signal is a plain dict built by a factory function in `signals.py`.
All signals carry:

| Field | Type | Description |
|---|---|---|
| `signal_type` | `str` | `'OSA'` or `'COMPLIANCE'` (or any new type) |
| `merge_key` | `tuple` | Controls merging — signals with the same key are collapsed into one |
| `store_id` | `int` | Store identifier |
| `trigger_types` | `list[str]` | e.g. `['WOW', 'VS_CHAIN']` after merging |

### OSA signal — `make_osa_signal()`

Produced by `osa_wow`, `osa_vs_chain`, `osa_repeat`.  
`merge_key = ('OSA', store_id, department)` — all three detectors can fire
for the same store-department and will be merged into one signal.

| Field | Type | Description |
|---|---|---|
| `department` | `str` | e.g. `'CHILLED'` |
| `this_week_lsv` | `float \| None` | £ lost sales this week |
| `last_week_osa` | `float \| None` | OSA % last week |
| `this_week_osa` | `float \| None` | OSA % this week |
| `wow_drift_pp` | `float \| None` | WoW OSA change in pp |
| `chain_this_week_osa` | `float \| None` | Chain average OSA % this week |
| `chain_gap_pp` | `float \| None` | Gap vs chain in pp (negative = below) |
| `chain_wow_drift_pp` | `float \| None` | Chain WoW OSA drift in pp |
| `repeat_item_count` | `int \| None` | Number of repeat-offender items |
| `repeat_item_details` | `list` | Per-item repeat detail dicts |

### Compliance signal — `make_compliance_signal()`

Produced by `tick_and_flick`.  
`merge_key = ('COMPLIANCE', store_id)` — store-level, no department.

| Field | Type | Description |
|---|---|---|
| `site_name` | `str` | Human-readable store name |
| `this_week_worked` | `int` | Alerts worked this week |
| `this_week_tf` | `int` | Tick-and-flick count this week |
| `this_week_tf_rate` | `float` | Tick-and-flick rate % this week |
| `last_week_worked` | `int` | Alerts worked last week |
| `last_week_tf` | `int` | Tick-and-flick count last week |
| `last_week_tf_rate` | `float` | Tick-and-flick rate % last week |
| `tf_rate_change` | `float` | pp change in TF rate WoW |
| `chain_tf_rate` | `float` | Chain-wide TF rate % this week |
| `above_chain_by` | `float` | pp above chain average |

---

## Merging

`_merge_signals` groups all signals by `merge_key`.  Signals with the same
key are collapsed into one using these rules:

- `trigger_types` lists are combined and deduped (order preserved)
- Numeric OSA fields take the non-`None` value; where both are present the
  later detector wins (`WOW → VS_CHAIN → REPEAT`)
- `this_week_lsv` takes the maximum across all signals for that key
- `repeat_item_count` / `repeat_item_details` are taken from the REPEAT
  detector

Signals with unique keys (e.g. COMPLIANCE) pass through untouched.

---

## Configuration — `DetectorConfig`

All thresholds have defaults defined in `DetectorConfig` in `config.py`.
Pass an instance to `detect_signals()` to override any subset:

```python
from alerts_pipeline.stages._1_detect.config import DetectorConfig
from alerts_pipeline.stages._1_detect.detect import detect_signals

cfg = DetectorConfig(
    min_wow_drop=0.05,
    min_lost_sales_value=500,
)
signals = detect_signals(osa, ..., config=cfg)
```

Use `dataclasses.replace` to build a variant from an existing config:

```python
from dataclasses import replace
strict_cfg = replace(cfg, min_chain_gap=0.08)
```

### Full field reference

| Field | Default | Detector(s) |
|---|---|---|
| `section` | `'DEPARTMENT_NAME'` | all OSA |
| `min_lost_sales_value` | `200.0` | WOW, VS_CHAIN |
| `min_wow_drop` | `0.01` | WOW |
| `min_chain_gap` | `0.03` | VS_CHAIN |
| `min_alert_weeks` | `4` | REPEAT |
| `min_osa_drop` | `0.05` | REPEAT |
| `min_weekly_lsv` | `50.0` | REPEAT |
| `min_wow_increase` | `0.10` | TICK_AND_FLICK |
| `min_chain_outperform` | `0.05` | TICK_AND_FLICK |
| `min_alerts_worked` | `5` | TICK_AND_FLICK |

---

## Detector Metadata — `DetectorInfo`

Every detector module exposes a `METADATA = DetectorInfo(...)` attribute.
The registry collects these into `registry.ALL_DETECTOR_INFO`.

```python
from alerts_pipeline.stages._1_detect import registry

for info in registry.ALL_DETECTOR_INFO:
    print(info.name)        # e.g. 'WOW'
    print(info.problem)     # what availability issue this surfaces
    print(info.action)      # what the store team should do
    print(info.baseline)    # what the metric is compared against
    print(info.logic)       # plain-English firing condition
    print(info.config_keys) # which DetectorConfig fields control it
```

---

## Adding a New Detector

1. **Create** `detectors/<name>.py` — the registry picks it up automatically.

2. **Define metadata:**
```python
from alerts_pipeline.stages._1_detect.config import DetectorInfo

METADATA = DetectorInfo(
    name        = 'MY_TRIGGER',
    problem     = 'What availability or compliance problem this surfaces.',
    action      = 'What the store team should do when it fires.',
    baseline    = 'What the metric is compared against.',
    logic       = 'Plain-English description of the firing conditions.',
    config_keys = ['relevant_config_field'],
)
```

3. **Implement `detect()`** — declare only the parameters you need; the
   pipeline passes kwargs by name so unused ones are ignored:
```python
def detect(osa, this_week_start, this_week_end, section, min_lost_sales_value):
    ...
```

4. **Build signals using a factory** from `signals.py`:
```python
from alerts_pipeline.stages._1_detect.signals import make_osa_signal

return [make_osa_signal(
    store_id      = ...,
    department    = ...,
    trigger_types = ['MY_TRIGGER'],
    this_week_lsv = ...,
)]
```

   For a new signal type, add a `make_<type>_signal()` factory to `signals.py`
   first, then use it here.

5. **Add thresholds** to `DetectorConfig` in `config.py` if needed, and
   reference them in `config_keys` on your `METADATA`.

No changes are needed to `detect.py`, `registry.py`, or any other file.
