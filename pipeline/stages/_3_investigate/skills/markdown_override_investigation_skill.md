# Markdown Override Investigation Skill

## Purpose
This skill guides the investigation of a `MARKDOWN_OVERRIDE` alert. A store has been overriding the markdown algorithm at a rate that is either significantly above the chain average (`VS_CHAIN`) or has risen sharply week-on-week (`WOW`). Overriding the algorithm means a member of staff manually changed the price that the system recommended, typically reducing it less than suggested — causing items to sit on the shelf longer and increasing waste risk.

---

## Key Signal Fields

| Field | Description |
|---|---|
| `this_week_override_rate` | % of markdowns overridden this week |
| `chain_override_rate` | Chain-wide override rate this week |
| `above_chain_pp` | pp above chain (VS_CHAIN trigger only) |
| `last_week_override_rate` | % overridden last week (WOW trigger only) |
| `wow_change_pp` | pp change WoW (WOW trigger only) |
| `this_week_total_markdowns` | Total markdown events this week |
| `this_week_overrides` | Number of overrides this week |

## Key Facts Fields (from Stage 2)

| Field | Description |
|---|---|
| `override_dept_breakdown` | Top departments by override count — `[{dept, total_markdowns, overrides, override_rate_pct}]` |

---

## Investigation Steps

### 1. Establish the scale
- How many markdowns were there this week? (`this_week_total_markdowns`)
- How many were overridden? (`this_week_overrides`)
- Is this a large store with many markdowns, or a small store where even a few overrides create a high rate?

### 2. Identify the trigger
- **VS_CHAIN**: The store's override rate is `above_chain_pp` pp above the chain average. Is this a persistent pattern or a one-week spike?
- **WOW**: The rate has jumped `wow_change_pp` pp in a single week. What changed this week? Was a specific person or department driving the increase?

### 3. Drill into departments
- Review `override_dept_breakdown` to find which departments have the highest override counts.
- Focus the recommended action on the top 1–2 departments by override count, not the overall store rate.

### 4. Consider intent
- A small number of overrides in a week is normal — staff may legitimately judge that an item is still sellable at a higher price.
- The alert fires when the rate is *disproportionate*. The narrative should frame this as a guidance-adherence issue, not an accusation.

---

## Narrative Construction Rules

### Title
- VS_CHAIN: `"Markdown override rate {this_week_override_rate}% — {above_chain_pp}pp above chain average"`
- WOW: `"Markdown override rate up {wow_change_pp}pp this week to {this_week_override_rate}%"`
- Both triggers merged: Use the VS_CHAIN framing with the WOW change in the detail box.

### Detail Box
- State the raw numbers: `"{this_week_overrides} of {this_week_total_markdowns} markdowns were overridden ({this_week_override_rate}%)."`
- For VS_CHAIN: `"Chain average is {chain_override_rate}% — this store is {above_chain_pp}pp above."`
- For WOW: `"Last week the rate was {last_week_override_rate}% — up {wow_change_pp}pp."`
- If dept breakdown is available: name the top 1–2 departments driving overrides.

### Recommended Action
- Always name the department if available: `"Review override decisions in [DEPT] with the store manager."`
- Include the guidance: `"Ensure markdown guidance is being followed. Overrides should only be made where there is a clear commercial reason."`
- Do **not** suggest the staff are acting in bad faith — frame as a guidance and training conversation.

### Cost If Not Fixed
- Overrides typically result in items sitting on shelf longer and eventually being wasted.
- Use: `"Items overridden at a higher price are at increased risk of reaching end-of-life unsold, driving unnecessary waste."` 
- Do **not** project a £ cost — the direct financial impact of override decisions is not directly measurable from this data.

---

## Do Not
- Do not name individual staff members.
- Do not suggest the store is deliberately gaming the system.
- Do not reference `store_id` or raw merge keys.
- Do not speculate about supply chain issues — this alert is about in-store pricing decisions only.
