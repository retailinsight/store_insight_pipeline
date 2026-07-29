# Waste Investigation Skill

## Purpose
This skill guides the investigation of a `WASTE` alert. It compares waste units with markdown units to identify stores where waste is high relative to markdown activity, either compared with the chain (`VS_CHAIN`) or with the prior week (`WOW`). It does not establish whether individual wasted units were marked down before disposal.

---

## Key Signal Fields

| Field | Description |
|---|---|
| `this_week_stb_rate` | Waste units as a % of markdown units this week; retained field name |
| `chain_stb_rate` | Chain-wide waste-to-markdown ratio this week; retained field name |
| `above_chain_pp` | pp above chain ratio (VS_CHAIN trigger only) |
| `last_week_stb_rate` | Store waste-to-markdown ratio last week (WOW trigger only) |
| `wow_change_pp` | pp change in the ratio WoW (WOW trigger only) |
| `this_week_waste_qty` | Total units wasted this week |
| `this_week_stb_qty` | Not available from the source data; do not use in a narrative |
| `this_week_waste_value` | £ value of all waste this week (at original price) |

## Key Facts Fields (from Stage 2)

| Field | Description |
|---|---|
| `waste_dept_breakdown` | Top departments by waste quantity and value — `[{dept, waste_qty, waste_value}]` |

---

## Investigation Steps

### 1. Establish the scale
- How many units were wasted? (`this_week_waste_qty`)
- What is the total waste value at original price? (`this_week_waste_value`) — this is the upper bound of what could have been recovered.
- How high is waste relative to markdown activity? (`this_week_stb_rate`)

### 2. Identify the trigger
- **VS_CHAIN**: The store's waste-to-markdown ratio is `above_chain_pp` pp above the chain average. Is this persistent or recent?
- **WOW**: The ratio has changed by `wow_change_pp` pp in a single week. Is a specific department or event driving the change?

### 3. Drill into departments
- Review `waste_dept_breakdown` to identify the departments with the most waste units and value.
- Focus the recommended action on the highest-impact departments.

### 4. Root cause framing
- A high waste-to-markdown ratio may reflect missed markdown opportunities, over-ordering, unsuitable markdown depth, or operational handling.
- The data cannot attribute individual waste units to a markdown history, so the narrative must frame these as investigation hypotheses rather than facts.

---

## Narrative Construction Rules

### Title
- VS_CHAIN: `"Waste-to-markdown ratio {this_week_stb_rate}% — {above_chain_pp}pp above chain average"`
- WOW: `"Waste-to-markdown ratio up {wow_change_pp}pp this week to {this_week_stb_rate}%"`
- Both triggers merged: Use the VS_CHAIN framing with the WOW change in the detail box.

### Detail Box
- State the raw numbers: `"{this_week_waste_qty} units were wasted this week, valued at £{this_week_waste_value} at original price."`
- State the contextual metric: `"Waste was {this_week_stb_rate}% of markdown volume this week."`
- For VS_CHAIN: `"Chain average waste-to-markdown ratio is {chain_stb_rate}% — this store is {above_chain_pp}pp above."`
- For WOW: `"Last week the waste-to-markdown ratio was {last_week_stb_rate}% — up {wow_change_pp}pp."`
- If department breakdown is available, name the top 1–2 departments by waste quantity and value.

### Recommended Action
- Name the department if available: `"Review waste and markdown processes in [DEPT] to identify missed markdown opportunities, over-ordering, or operational handling issues."`
- Do not state that items were binned before markdown was applied.

### Cost If Not Fixed
- `this_week_waste_value` is the original-price value of all waste, not a confirmed recoverable markdown opportunity.
- Frame as: `"Items worth approximately £{this_week_waste_value} at original price were wasted this week. Review whether some could have been recovered through earlier markdown action."`
- Do not imply all waste value was recoverable.

---

## Do Not
- Do not call this measure straight-to-bin or imply that individual waste units bypassed markdown.
- Do not use `this_week_stb_qty`; it is unavailable from the source data.
- Do not imply that all original-price waste value was recoverable.
- Do not suggest the store is deliberately wasting stock.
- Do not reference `store_id` or raw merge keys.
- Do not project multi-week costs unless explicitly asked — the single-week figure is sufficient.
