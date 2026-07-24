# Investigation Skill: OSA Recurring Slot Alert

## Purpose

Guide the investigation of an `OSA_RECURRING_SLOT` alert: a store-department that repeatedly loses sales in a specific day-of-week + reporting-period slot (e.g. Monday mornings).

Use this skill alongside the Smart Action Card Content Skill to generate card content that is specific, commercially grounded, and actionable for a store manager.

---

## When This Skill Applies

Signal type: **OSA_RECURRING_SLOT**
Trigger type: **RECURRING_SLOT**

A signal fires when at least two items in a store-department show a recurring lost-sales pattern in the same `(day-of-week, reporting_period)` slot across multiple weeks.

---

## Investigation Steps

### 1. Establish the commercial scale
- Start with `avg_weekly_lsv` and `total_lsv` on the signal.
- Calculate the 4-week projection: `avg_weekly_lsv × projection_weeks`.
- This sets the stakes. If the weekly LSV is low, the recommended action should be proportionally lighter.

### 2. Characterise the recurring slot
- Identify `dow_name` and `period_label` — the specific slot with the problem (e.g. "Monday Morning").
- Use `repeat_item_count` and `repeat_item_details` to see how many items and which items drive the pattern.
- Each item detail includes `repeat_weeks` and `total_lsv` — longer-running patterns are more entrenched.

### 3. Check trend and share
- `slot_trend` from facts: is the slot getting worse, better, or flat?
- `recurring_slot_share_pct`: what share of the slot's total lost sales is explained by the recurring items?
- `slot_share_of_dept_total_pct`: what share of the whole department's lost sales is this slot responsible for?
- A high and worsening share means the slot is a priority for operational intervention.

### 4. Review weekly slot history
- `slot_history` from facts gives week-by-week LSV, sales volume, and OSA for the slot.
- Look for step changes (e.g., a new delivery schedule or staffing rota) and sustained spikes.
- Name the last 1–3 weeks in the explanation if the trend is notable.

### 5. Identify operational drivers
The trigger is time-specific, so investigate operational causes tied to that slot:
- Delivery timing: does the delivery arrive after the slot starts?
- Shelf-filling routines: is the department restocked before the busy period?
- Staffing levels: are there enough colleagues on the shop floor during the slot?
- Demand spikes: is there a known weekly event (promotions, local market) that coincides with the slot?

---

## Narrative Construction Rules

### Title slot
- Lead with the store, department, and the specific slot.
- Example: `Store 42 Produce: recurring lost sales on Monday mornings`

### Explanation slot
- Open with the number of items, the slot, and the total lost sales value over the lookback.
- Include `avg_weekly_lsv` to give a weekly commercial scale.
- Add trend and share facts if they strengthen the case.
- List the top 1–3 recurring items by total LSV. Do not fabricate items not in `repeat_item_details`.

### Recommended Action slot
- Name the department and the slot.
- Focus on operational causes tied to the specific time: delivery timing, shelf-filling, staffing, or demand.
- If the trend is worsening, escalate to the area manager or supply-chain team.

### Cost if Not Fixed slot
- Single sentence: `If this recurring slot problem continues, the store could lose approximately £X over the next N weeks.`
- Use `avg_weekly_lsv × projection_weeks` from the signal/scorer.

---

## What NOT to Do

- Do not reference trigger type names (`RECURRING_SLOT`) in the card — use plain English.
- Do not fabricate product names, £ figures, or percentages not present in the signal/facts.
- Do not treat this as a generic OSA alert; the time-specific nature is the key insight.
- Do not omit the £ projection from the cost panel.
