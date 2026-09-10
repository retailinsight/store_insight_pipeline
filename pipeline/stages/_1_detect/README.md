# Stage 1 — Detection (`_1_detect`)

Runs all registered detectors against the OSA and feedback data, merges
signals that share the same logical key, and returns a flat list of signal
dicts for the rest of the pipeline.

---

## Architecture

```
_1_detect/
├── detect.py            Public entry point — detect_signals()
├── registry.py          Auto-discovers detectors/ and exposes ALL_DETECTORS / ALL_DETECTOR_INFO
├── detector_info.py     DetectorInfo dataclass — per-detector metadata schema
├── protocols.py         Shared protocol definitions
├── signals.py           Signal factories — make_osa_signal(), make_compliance_signal(),
│                        make_markdown_override_signal(), make_waste_signal(),
│                        make_markdown_sellthrough_signal(), make_markdown_sku_signal()
└── detectors/
    ├── osa/
    │   ├── wow.py
    │   ├── vs_chain.py
    │   └── repeat.py
    ├── compliance/
    │   ├── tick_and_flick_wow.py
    │   └── tick_and_flick_vs_chain.py
    ├── markdown_override/
    │   ├── wow.py
    │   └── vs_chain.py
    ├── markdown_sellthrough/
    │   ├── wow.py
    │   └── vs_chain.py
    ├── markdown_sku/
    │   ├── repeat_request.py
    │   └── excessive_override.py
    └── waste/
        ├── wow.py
        └── vs_chain.py
```

Thresholds live in `DetectorConfig` at `pipeline/pipeline/config.py`.

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
| `signal_type` | `str` | `'OSA'`, `'COMPLIANCE'`, `'MARKDOWN_OVERRIDE'`, `'WASTE'`, `'MARKDOWN_SELLTHROUGH'`, `'MARKDOWN_SKU'` (or any new type) |
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

Produced by `compliance/tick_and_flick_wow` and `compliance/tick_and_flick_vs_chain`.
`merge_key = ('COMPLIANCE', store_id)` — store-level, no department; the two
sub-detectors merge into a single signal when both fire.

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

### Markdown-override signal — `make_markdown_override_signal()`

Produced by `markdown_override/wow` and `markdown_override/vs_chain`.  
`merge_key = ('MARKDOWN_OVERRIDE', store_id)` — store-level.

| Field | Type | Description |
|---|---|---|
| `site_name` | `str` | Human-readable store name |
| `this_week_override_rate` | `float` | Override % this week (0–100) |
| `last_week_override_rate` | `float \| None` | Override % last week |
| `wow_change_pp` | `float \| None` | WoW change in pp |
| `chain_override_rate` | `float \| None` | Chain average override % |
| `above_chain_pp` | `float \| None` | pp above chain average |
| `this_week_total_markdowns` | `int` | Total markdown events this week |
| `this_week_overrides` | `int` | Overridden markdowns this week |

### Waste signal — `make_waste_signal()`

Produced by `waste/wow` and `waste/vs_chain`.  
`merge_key = ('WASTE', store_id)` — store-level.

| Field | Type | Description |
|---|---|---|
| `site_name` | `str` | Human-readable store name |
| `this_week_stb_rate` | `float` | Straight-to-bin % this week (0–100) |
| `last_week_stb_rate` | `float \| None` | STB % last week |
| `wow_change_pp` | `float \| None` | WoW change in pp |
| `chain_stb_rate` | `float \| None` | Chain average STB % |
| `above_chain_pp` | `float \| None` | pp above chain average |
| `this_week_waste_qty` | `int` | Total units wasted this week |
| `this_week_stb_qty` | `int` | Units straight-to-bin this week |
| `this_week_waste_value` | `float` | £ value of waste this week |

### Markdown sell-through signal — `make_markdown_sellthrough_signal()`

Produced by `markdown_sellthrough/wow` and `markdown_sellthrough/vs_chain`.  
`merge_key = ('MARKDOWN_SELLTHROUGH', store_id)` — store-level.

| Field | Type | Description |
|---|---|---|
| `site_name` | `str` | Human-readable store name |
| `this_week_sellthrough_rate` | `float` | Sell-through % this week (0–100) |
| `last_week_sellthrough_rate` | `float \| None` | Sell-through % last week |
| `wow_change_pp` | `float \| None` | WoW change in pp |
| `chain_sellthrough_rate` | `float \| None` | Chain average sell-through % |
| `below_chain_pp` | `float \| None` | pp below chain average |
| `this_week_markdown_qty` | `int` | Markdown units this week |
| `this_week_markdown_value` | `float` | £ markdown sales this week |

### Markdown SKU signal — `make_markdown_sku_signal()`

Produced by `markdown_sku/repeat_request` and `markdown_sku/excessive_override`.  
`merge_key = ('MARKDOWN_SKU', store_id, item_id)` — store-SKU level. Both triggers can fire for the same store-SKU and will be merged.

| Field | Type | Description |
|---|---|---|
| `site_name` | `str` | Human-readable store name |
| `item_id` | `int` | SKU identifier |
| `item_description` | `str` | Human-readable item name |
| `department` | `str` | Department name |
| `markdown_request_count` | `int \| None` | Times this SKU was marked down in the window |
| `override_count` | `int \| None` | Times this SKU's markdown was overridden |
| `lookback_weeks` | `int` | Rolling window length |
| `avg_markdown_pct` | `float \| None` | Average markdown depth % |

---

## Merging

`_merge_signals` groups all signals by `merge_key`.  Signals with the same
key are collapsed into one using these rules:

- `trigger_types` lists are combined and deduped (order preserved)
- For OSA: numeric fields take the non-`None` value; where both are present the
  later detector wins (`WOW → VS_CHAIN → REPEAT`); `this_week_lsv` takes the
  maximum across all signals for that key; `repeat_item_count` /
  `repeat_item_details` are taken from the REPEAT detector
- For MARKDOWN_OVERRIDE / WASTE / MARKDOWN_SELLTHROUGH: WOW and VS_CHAIN
  signals for the same store share a `merge_key` and are collapsed — numeric
  fields take non-`None` values, trigger types are combined
- For MARKDOWN_SKU: REPEAT_REQUEST and EXCESSIVE_OVERRIDE signals for the
  same `(store_id, item_id)` are merged; `markdown_request_count` and
  `override_count` are taken from the respective detector that set them

Signals with unique keys pass through untouched.

---

## Configuration — `DetectorConfig`

All thresholds have defaults defined in `DetectorConfig` in `config.py`.
Pass an instance to `detect_signals()` to override any subset:

```python
from store_insight.pipeline.pipeline.config import DetectorConfig
from store_insight.pipeline.stages._1_detect.detect import detect_signals

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

### Configuration Compatibility

The `detect_signals()` function supports both dictionary and Pydantic model configurations:

```python
# Dictionary configuration (used in tests)
cfg_dict = {'detectors': {'enabled': ['osa.wow']}}
signals = detect_signals(osa, ..., cfg=cfg_dict)

# Pydantic model configuration (production)
from store_insight.pipeline.pipeline.config import DetectorConfig
cfg_model = DetectorConfig(min_wow_drop=0.05)
signals = detect_signals(osa, ..., config=cfg_model)
```

The function automatically detects the input type and handles detector filtering appropriately.

### Full field reference

| Field | Default | Detector(s) |
|---|---|---|
| `section` | `'DEPARTMENT_NAME'` | all OSA |
| `min_lost_sales_value` | `200.0` | OSA WOW, OSA VS_CHAIN |
| `min_wow_drop` | `0.01` | OSA WOW |
| `min_chain_gap` | `0.03` | OSA VS_CHAIN |
| `min_alert_weeks` | `4` | OSA REPEAT |
| `min_osa_drop` | `0.05` | OSA REPEAT |
| `min_weekly_lsv` | `50.0` | OSA REPEAT |
| `min_compliance_wow_drop` | `0.10` | TICK_AND_FLICK WOW |
| `min_compliance_chain_gap` | `0.05` | TICK_AND_FLICK VS_CHAIN |
| `min_alerts_worked` | `5` | TICK_AND_FLICK (both) |
| `min_override_chain_gap` | `0.05` | MARKDOWN_OVERRIDE VS_CHAIN |
| `min_override_wow_increase` | `0.05` | MARKDOWN_OVERRIDE WOW |
| `min_total_markdowns` | `10` | MARKDOWN_OVERRIDE (both) |
| `min_stb_chain_gap` | `0.05` | WASTE VS_CHAIN |
| `min_stb_wow_increase` | `0.05` | WASTE WOW |
| `min_waste_qty` | `5` | WASTE (both) |
| `min_sellthrough_chain_gap` | `0.05` | MARKDOWN_SELLTHROUGH VS_CHAIN |
| `min_sellthrough_wow_drop` | `0.05` | MARKDOWN_SELLTHROUGH WOW |
| `min_markdown_qty` | `10` | MARKDOWN_SELLTHROUGH (both) |
| `lookback_weeks` | `4` | MARKDOWN_SKU (both) |
| `min_markdown_weeks` | `3` | MARKDOWN_SKU REPEAT_REQUEST |
| `min_markdown_requests` | `8` | MARKDOWN_SKU REPEAT_REQUEST |
| `min_sku_override_rate` | `0.50` | MARKDOWN_SKU EXCESSIVE_OVERRIDE |
| `min_sku_requests` | `3` | MARKDOWN_SKU EXCESSIVE_OVERRIDE |

---

## Detector Metadata — `DetectorInfo`

Every detector module exposes a `METADATA = DetectorInfo(...)` attribute.
The registry collects these into `registry.ALL_DETECTOR_INFO`.

```python
from store_insight.pipeline.stages._1_detect import registry

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

1. **Create** `detectors/<alert_type>/<name>.py` — the registry picks it up automatically.

2. **Define metadata:**
```python
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo

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
from store_insight.pipeline.stages._1_detect.signals import make_osa_signal

return [make_osa_signal(
    store_id      = ...,
    department    = ...,
    trigger_types = ['MY_TRIGGER'],
    this_week_lsv = ...,
)]
```

   For a new signal type, add a `make_<type>_signal()` factory to `signals.py`
   first, then use it here.

5. **Add thresholds** to `DetectorConfig` in `pipeline/pipeline/config.py`
   if needed, mirror the defaults in `config/base/default.yaml` under the
   relevant `thresholds:` sub-block, and reference them in `config_keys`
   on your `METADATA`.

No changes are needed to `detect.py`, `registry.py`, or any other file.
