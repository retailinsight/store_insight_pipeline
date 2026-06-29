# Waste Investigation Skill

## Purpose
This skill guides the investigation of a `WASTE` alert. A store's straight-to-bin (STB) rate — the proportion of wasted items that were never marked down before being discarded — is either significantly above the chain average (`VS_CHAIN`) or has risen sharply week-on-week (`WOW`). Straight-to-bin waste represents a direct, recoverable loss: items that could have been sold at a reduced price were instead binned.

---

## Key Signal Fields

| Field | Description |
|---|---|
| `this_week_stb_rate` | % of wasted items going straight to bin this week |
| `chain_stb_rate` | Chain-wide STB rate this week |
| `above_chain_pp` | pp above chain (VS_CHAIN trigger only) |
| `last_week_stb_rate` | STB rate last week (WOW trigger only) |
| `wow_change_pp` | pp change WoW (WOW trigger only) |
| `this_week_waste_qty` | Total units wasted this week |
| `this_week_stb_qty` | Units going straight to bin this week |
| `this_week_waste_value` | £ value of all waste this week (at original price) |

## Key Facts Fields (from Stage 2)

| Field | Description |
|---|---|
| `waste_dept_breakdown` | Top departments by STB quantity — `[{dept, waste_qty, stb_qty, stb_rate_pct, waste_value}]` |

---

## Investigation Steps

### 1. Establish the scale
- How many units were wasted? (`this_week_waste_qty`)
- What proportion went straight to bin? (`this_week_stb_qty` / `this_week_waste_qty`)
- What is the total waste value at original price? (`this_week_waste_value`) — this is the upper bound of what could have been recovered.

### 2. Identify the trigger
- **VS_CHAIN**: The store's STB rate is `above_chain_pp` pp above the chain average. Is this a persistent structural problem or a recent change?
- **WOW**: The rate has jumped `wow_change_pp` pp in a single week. Is a specific department or event driving the spike?

### 3. Drill into departments
- Review `waste_dept_breakdown` to identify the worst-performing departments by STB quantity and value.
- Focus the recommended action on the highest-impact departments.

### 4. Root cause framing
- STB waste usually means items reached end-of-life without ever being flagged for markdown — either because:
  - The markdown process wasn't followed (items missed)
  - Items were over-ordered and the markdown algorithm couldn't clear them in time
  - Staff are binning items without following the markdown step
- The narrative should prompt investigation of *which* explanation applies here.

---

## Narrative Construction Rules

### Title
- VS_CHAIN: `"Straight-to-bin waste {this_week_stb_rate}% — {above_chain_pp}pp above chain average"`
- WOW: `"Straight-to-bin rate up {wow_change_pp}pp this week to {this_week_stb_rate}%"`
- Both triggers merged: Use the VS_CHAIN framing with the WOW change in the detail box.

### Detail Box
- State the raw numbers: `"{this_week_stb_qty} of {this_week_waste_qty} wasted units ({this_week_stb_rate}%) went straight to bin this week."`
- For VS_CHAIN: `"Chain average STB rate is {chain_stb_rate}% — this store is {above_chain_pp}pp above."`
- For WOW: `"Last week the rate was {last_week_stb_rate}% — up {wow_change_pp}pp."`
- If dept breakdown available: name the top 1–2 departments by STB quantity.

### Recommended Action
- Name the department if available: `"Review end-of-life processes in [DEPT] — ensure items flagged for markdown are being actioned before they reach their waste date."`
- `"Check whether the markdown algorithm is being followed and items are not being binned before markdown is applied."`

### Cost If Not Fixed
- Straight-to-bin waste has a directly quantifiable opportunity cost.
- Use `this_week_waste_value` as the upper bound of recoverable value.
- Frame as: `"If left unaddressed, items worth approximately £{this_week_waste_value} per week are being discarded that could have generated revenue through markdowns."` 
- Note that not all waste value is recoverable — markdown revenue is typically 30–70% of original price.

---

## Do Not
- Do not conflate total waste with STB waste — some waste is unavoidable (e.g. damaged items).
- Do not suggest the store is deliberately wasting stock.
- Do not reference `store_id` or raw merge keys.
- Do not project multi-week costs unless explicitly asked — the single-week figure is sufficient.
