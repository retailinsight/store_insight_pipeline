# Investigation Skill: OSA Availability Alert

## Purpose
Guide the investigation of an OSA (on-shelf availability) alert for a store-department.
Use this skill alongside the Smart Action Card Content Skill to generate card content
that is specific, commercially grounded, and actionable for a store manager.

---

## When This Skill Applies

Signal type: **OSA**
Trigger types (one or more may be present on the same signal):

| Trigger | What it means |
|---|---|
| `WOW` | Store OSA dropped week-on-week beyond the threshold |
| `VS_CHAIN` | Store OSA is materially below the chain average this week |
| `REPEAT` | One or more items have triggered availability alerts for N consecutive weeks |

A signal may carry multiple triggers (e.g. WOW + VS_CHAIN). Investigate all present triggers;
the one with the strongest commercial impact should lead the narrative.

---

## Investigation Steps

### 1. Establish the commercial scale
- Start with `this_week_lsv` — the total lost sales value for the department this week.
- Calculate the 4-week projection: `this_week_lsv × projection_weeks`.
- This sets the stakes. If LSV is low, the recommended action should be proportionally lighter.

### 2. Characterise the OSA movement (WOW trigger)
- Compare `this_week_osa` vs `last_week_osa` — the `wow_drift_pp` field gives the signed change.
- Check `chain_drift_pp` from facts: if the chain also fell, the store may be moving with a wider
  pattern rather than an isolated problem. Name this in the explanation if relevant.
- A large store drop with a flat chain = isolated store issue → stronger recommended action.

### 3. Benchmark against the chain (VS_CHAIN trigger)
- Use `chain_gap_pp` — the gap between store OSA and chain average this week.
- Use `chain_this_week_osa` from facts for the absolute chain figure.
- A persistent gap (VS_CHAIN without WOW) suggests a structural availability problem
  rather than a sudden event.

### 4. Identify the worst-affected products
- `subclass_contributors` (from `osa_ppg_drilldown`): top PPGs by this-week LSV.
  → Answers: *which products are losing the most sales right now?*
- `subclass_changes` (from `osa_ppg_drilldown`): top PPGs by WoW LSV increase.
  → Answers: *which products are getting worse?*
- Name the top 1–3 contributors in the detail box. Do not fabricate items not in the list.

### 5. Identify the worst day (DOW pattern)
- `dow_pattern` (from `osa_dow`): lost sales by day of week, sorted descending.
- `worst_day` is the first element — use it in the recommended action timing.
- If no DOW data is available, omit the day reference entirely.

### 6. Investigate repeat offenders (REPEAT trigger only)
- `repeat_item_history` (from `osa_repeat_history`): per-item weekly OSA and LSV history.
- `repeat_item_details` on the signal: list of items with `alert_weeks` and `cumulative_lsv`.
- `repeat_item_count`: number of persistently failing items.
- For REPEAT signals, the recommended action must address root cause
  (replenishment parameters, supplier lead times, on-shelf capacity) — not just daily checks.

---

## Narrative Construction Rules

### Title slot
- Lead with the strongest trigger. Priority order: REPEAT > VS_CHAIN > WOW.
- Include the key magnitude: pp drop, pp gap, or number of repeat items.
- Example: `BEERS & LAGERS: 3 items with persistent availability issues`

### Explanation slot
- Open with the £ lost sales figure.
- Add OSA context for WOW/VS_CHAIN triggers (store vs chain, drift).
- Add repeat item count for REPEAT triggers, then list top items.
- Close with the worst-day callout if available.

### Recommended Action slot
- Name the department.
- Include a timing element (e.g. "before 8am daily", "before store opens").
- For WOW/VS_CHAIN: focus on replenishment discipline and gap-filling.
- For REPEAT: focus on root-cause investigation (parameters, lead times, capacity).
- Include worst-day callout if available.

### Cost if Not Fixed slot
- Single sentence: `If this continues at the same rate, the store could lose approximately £X in the next N weeks.`
- Use `cost_projection` and `projection_weeks` from facts directly.

---

## What NOT to Do

- Do not reference trigger type names (`WOW`, `VS_CHAIN`, `REPEAT`) in the card — use plain English.
- Do not fabricate product names, £ figures, or OSA percentages not present in the signal data.
- Do not use vague language ("significant issue", "notable drop") — always quantify.
- Do not omit the £ projection from the cost panel.
