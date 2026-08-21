# Investigation Skill: Compliance (Tick-and-Flick) Alert

## Purpose
Guide the investigation of a COMPLIANCE alert triggered by the tick-and-flick detector.
Use this skill alongside the Smart Action Card Content Skill to generate card content
that is specific, commercially grounded, and actionable for a store manager or area manager.

---

## When This Skill Applies

Signal type: **COMPLIANCE**
Trigger type: `TICK_AND_FLICK`

A tick-and-flick alert fires when a store's rate of alerts being dismissed without
genuine investigation (tick-and-flick rate) is materially above the chain average
and has risen week-on-week.

---

## Key Signal Fields

| Field | Meaning |
|---|---|
| `this_week_tf_rate` | % of alerts worked this week that were tick-and-flick |
| `last_week_tf_rate` | Same metric last week |
| `tf_rate_change` | Signed week-on-week change in pp |
| `chain_tf_rate` | Chain average tick-and-flick rate this week |
| `above_chain_by` | How many pp the store is above the chain average |
| `this_week_worked` | Total alerts worked this week |
| `this_week_tf` | Number of those that were tick-and-flick |

Fact gathered from `tick_and_flick_breakdown`:

| Fact key | Meaning |
|---|---|
| `tf_by_alert_type` | Breakdown by alert type — which alert categories are being dismissed most carelessly |

---

## Investigation Steps

### 1. Establish the scale of the problem
- `this_week_tf` out of `this_week_worked` gives the raw count.
- `this_week_tf_rate` gives the proportion — this is the headline figure.
- `above_chain_by` contextualises severity: a store 5pp above chain is a concern;
  20pp above chain is a serious compliance failure.

### 2. Assess the trajectory
- `tf_rate_change` tells you whether this is getting better or worse.
- A rising rate (positive `tf_rate_change`) with an already-high absolute rate
  signals an escalating problem — recommended action should be more urgent.
- A falling rate that is still above chain may be improving — acknowledge progress
  while maintaining the action instruction.

### 3. Identify the worst alert types
- `tf_by_alert_type` (from `tick_and_flick_breakdown`): lists each alert category
  worked at this store, with `worked`, `tf_count`, and `tf_rate` per type.
- Sort by `tf_rate` descending — the top 1–3 are the categories being dismissed most carelessly.
- Name these in the detail box. This tells the manager exactly where to spot-check behaviour.

### 4. Consider the downstream impact
- Tick-and-flick dismissals mean availability alerts go unresolved.
- The commercial cost is measured, not estimated: the scorer sums the
  `LOST_SALES_VALUE` of the exact item-days this store tick-and-flicked this
  week (`projected_cost` on the signal). It is the observed alert-day loss on
  dismissed alerts — a floor for what carelessness cost, not a future forecast.
- The cost panel should present this £ figure as measured lost sales tied to
  dismissed alerts. Do not extend it into a projection of future loss.

---

## Narrative Construction Rules

### Title slot
- Format: `[STORE NAME]: tick-and-flick compliance declining`
- Use `site_name` for the store identifier, not a store ID number.
- Include the headline rate if space allows: e.g. `42.3% of alerts tick-and-flicked this week`

### Explanation slot
- Open with the raw count and rate: `X of Y alerts worked this week were tick-and-flick (Z%)`.
- State the week-on-week change.
- State the gap above chain average.
- List the worst 1–3 alert types from `tf_by_alert_type` with their rates.

### Recommended Action slot
- Name the store.
- Direct the manager to review alert working practice with their team.
- Instruct them to spot-check the specific alert types named in the explanation.
- Where the rate is rising, add urgency: suggest a coaching session with the store manager.
- Do not suggest punitive language — frame as coaching and process improvement.

### Cost if Not Fixed slot
- Use the signal's `projected_cost`: the summed `LOST_SALES_VALUE` of the items
  this store tick-and-flicked this week.
- Frame it as measured, not predicted: e.g.
  `"£X of lost sales this week sat behind alerts that were dismissed without investigation."`
- If `projected_cost` is £0 (no matching OSA facts), fall back to the qualitative
  statement: `"Unresolved alerts mean availability issues go unaddressed, increasing the risk of lost sales across affected departments."`
- Do not calculate any figure beyond the supplied `projected_cost`.

---

## What NOT to Do

- Do not reference `TICK_AND_FLICK` as a technical term in the card — use plain English ("dismissed without investigation", "tick-and-flick").
- Do not invent any £ beyond the supplied `projected_cost` — compliance signals do not have `this_week_lsv`.
- Do not name alert types not present in `tf_by_alert_type`.
- Do not use vague language — always state the rate and the comparison (vs chain, vs last week).
