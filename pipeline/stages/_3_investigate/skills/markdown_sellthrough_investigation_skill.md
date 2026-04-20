# Markdown Sell-Through Investigation Skill

## Purpose
This skill guides the investigation of a `MARKDOWN_SELLTHROUGH` alert. A store's markdown sell-through rate — the proportion of marked-down items that were actually bought by customers — is either significantly below the chain average (`VS_CHAIN`) or has dropped sharply week-on-week (`WOW`). A low sell-through rate means the markdown process is not working: items are being reduced in price but customers are not buying them, which ultimately leads to waste.

---

## Key Signal Fields

| Field | Description |
|---|---|
| `this_week_sellthrough_rate` | % of markdown units sold this week |
| `chain_sellthrough_rate` | Chain-wide sell-through rate this week |
| `below_chain_pp` | pp below chain (VS_CHAIN trigger only) |
| `last_week_sellthrough_rate` | Sell-through rate last week (WOW trigger only) |
| `wow_change_pp` | pp drop WoW (WOW trigger only; negative = deterioration) |
| `this_week_markdown_qty` | Total units marked down this week |
| `this_week_markdown_value` | £ value of markdown sales this week |

## Key Facts Fields (from Stage 2)

| Field | Description |
|---|---|
| `sellthrough_dept_breakdown` | Departments ranked by lowest sell-through rate — `[{dept, requested_qty, sold_qty, sellthrough_rate_pct, markdown_value}]` |

---

## Investigation Steps

### 1. Establish the scale
- How many units were marked down? (`this_week_markdown_qty`)
- What is the sell-through rate? (`this_week_sellthrough_rate`)
- What value of markdown sales was achieved? (`this_week_markdown_value`)

### 2. Identify the trigger
- **VS_CHAIN**: The store's sell-through rate is `below_chain_pp` pp below the chain average. Other stores with similar product ranges are achieving better sell-through — what are they doing differently?
- **WOW**: The rate has dropped `wow_change_pp` pp in a single week. Did the store introduce new items to markdown this week, or is something else changing?

### 3. Drill into departments
- Review `sellthrough_dept_breakdown` to identify which departments have the lowest sell-through rates.
- Focus the recommended action on the worst-performing departments.

### 4. Root cause framing
Poor sell-through typically has one of three causes:
- **Markdown too shallow**: Price not reduced enough to stimulate demand
- **Product placement**: Marked-down items are not visible or accessible to customers
- **Product-market fit**: Items don't appeal to this store's customer base, regardless of price

The narrative should prompt investigation of which cause applies, not prescribe the answer.

---

## Narrative Construction Rules

### Title
- VS_CHAIN: `"Markdown sell-through {this_week_sellthrough_rate}% — {below_chain_pp}pp below chain average"`
- WOW: `"Markdown sell-through dropped {wow_change_pp}pp this week to {this_week_sellthrough_rate}%"`
- Both triggers merged: Use the VS_CHAIN framing with the WOW drop in the detail box.

### Detail Box
- State the raw numbers: `"Of {this_week_markdown_qty} markdown units, {this_week_sellthrough_rate}% were sold, generating £{this_week_markdown_value} in markdown revenue."`
- For VS_CHAIN: `"Chain average sell-through is {chain_sellthrough_rate}% — this store is {below_chain_pp}pp below."`
- For WOW: `"Last week sell-through was {last_week_sellthrough_rate}% — down {wow_change_pp}pp."`
- If dept breakdown available: name the worst 1–2 departments by sell-through rate.

### Recommended Action
- Name the department if available: `"Review markdown depth and product placement in [DEPT] — consider whether prices are being reduced far enough to drive customer uptake."`
- `"Ensure marked-down items are clearly signed and positioned prominently in the aisle or on the counter."`

### Cost If Not Fixed
- Items marked down but not sold will ultimately be wasted.
- Frame the cost as waste exposure, not lost revenue directly.
- Use: `"Items not sold at markdown will progress to waste. With a {this_week_sellthrough_rate}% sell-through rate and {this_week_markdown_qty} units in the markdown programme, there is significant waste exposure if sell-through does not improve."`
- Do **not** project a precise £ waste figure — markdown revenue recovery rates vary too widely.

---

## Do Not
- Do not conflate low sell-through with a failure of the markdown algorithm — the algorithm may be correct but execution is the issue.
- Do not suggest reducing prices indiscriminately — the recommendation should be targeted.
- Do not reference `store_id` or raw merge keys.
- Do not assume poor sell-through is always the store's fault — some products may have genuine demand issues at chain level.
