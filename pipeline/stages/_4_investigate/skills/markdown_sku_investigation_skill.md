# Markdown SKU Investigation Skill

## Purpose
This skill guides the investigation of a `MARKDOWN_SKU` alert. This is a SKU-level alert fired when a specific item at a specific store shows a persistent markdown problem over a rolling window:

- **REPEAT_REQUEST**: The markdown algorithm has flagged this item for reduction on 3+ distinct weeks, indicating a chronic surplus — the store keeps receiving more of this item than it can sell at full price.
- **EXCESSIVE_OVERRIDE**: Staff at this store are overriding the algorithm's price recommendation for this specific item on more than 50% of occasions, suggesting persistent resistance to the guidance for this SKU.

Unlike the store-level alerts (MARKDOWN_OVERRIDE, WASTE, MARKDOWN_SELLTHROUGH), this alert is about a *single item* and warrants a targeted SKU-level conversation.

---

## Key Signal Fields

| Field | Description |
|---|---|
| `item_id` | Internal item identifier |
| `item_description` | Human-readable item name |
| `department` | Department this item belongs to |
| `markdown_request_count` | Total markdown requests for this item in the window |
| `override_count` | Number of those requests that were overridden (EXCESSIVE_OVERRIDE only) |
| `lookback_weeks` | Rolling window length in weeks |
| `avg_markdown_pct` | Average markdown depth % over the window |

## Key Facts Fields (from Stage 2)

| Field | Description |
|---|---|
| `sku_markdown_history` | Week-by-week history — `[{week_start, request_count, override_count, avg_markdown_pct}]` ordered oldest to newest |

---

## Investigation Steps

### 1. Identify the item
- What is the item? (`item_description`, `department`)
- How many times has it appeared in the markdown programme over `lookback_weeks` weeks? (`markdown_request_count`)

### 2. Understand the trigger

**REPEAT_REQUEST**:
- The algorithm keeps flagging this item because it is not selling through at full price.
- Look at `sku_markdown_history` — is the request happening every week, or sporadically?
- Is the markdown depth increasing over time (avg_markdown_pct getting larger)? This suggests the item is getting harder to sell.
- Root causes: over-ordering, poor ranging for this store's customer base, or a seasonal item past its peak.

**EXCESSIVE_OVERRIDE**:
- Staff are regularly overriding the recommended markdown for this specific item.
- Look at `override_count` vs `markdown_request_count` — what is the override rate?
- Is the override happening consistently across all weeks in `sku_markdown_history`?
- Root causes: staff believe the item is worth more than the algorithm suggests, or there is a pricing policy misunderstanding for this item.

### 3. Assess the pattern from history
- Review `sku_markdown_history` for trend: is the problem getting worse, stable, or improving?
- If improving in the most recent week, consider whether the alert is still actionable.

---

## Narrative Construction Rules

### Title
- REPEAT_REQUEST: `"[item_description] marked down {markdown_request_count} times in {lookback_weeks} weeks"`
- EXCESSIVE_OVERRIDE: `"[item_description] overridden {override_count} of {markdown_request_count} markdown requests in {lookback_weeks} weeks"`
- Both triggers merged: Lead with EXCESSIVE_OVERRIDE if present, add repeat context.

### Detail Box
- State the item clearly: `"[item_description] ([department])"`
- REPEAT_REQUEST: `"This item has been flagged for markdown on {markdown_request_count} occasions over the last {lookback_weeks} weeks, with an average markdown depth of {avg_markdown_pct}%."`
- EXCESSIVE_OVERRIDE: `"The markdown recommendation for this item has been overridden {override_count} of {markdown_request_count} times — a {override_rate}% override rate."`
- If history shows a trend (e.g. every week): note the pattern explicitly.

### Recommended Action
- REPEAT_REQUEST: `"Review the ordering and ranging for [item_description] in [department]. Consider whether this item is suited to this store's customer profile, or whether ordering quantities should be reduced."`
- EXCESSIVE_OVERRIDE: `"Discuss the pricing guidance for [item_description] with the store manager. If the algorithm recommendation is consistently wrong for this item, escalate to the buying team for a review of the markdown parameters."`

### Cost If Not Fixed
- For REPEAT_REQUEST: repeated markdown requests mean the item is chronically over-ordered or unsuited to this store.
  - Use: `"An item requiring markdown every week represents a recurring ordering cost and waste risk. If quantities are not adjusted, this pattern is likely to continue."`
- For EXCESSIVE_OVERRIDE: items overridden may sell more slowly and ultimately be wasted.
  - Use: `"Consistently overriding the recommended markdown means this item is likely to sell at a slower rate, increasing its risk of reaching end-of-life unsold."`
- Do **not** project a £ cost — SKU-level waste projections require volume data not available in this signal.

---

## Do Not
- Do not name individual staff members.
- Do not reference `item_id`, `store_id`, or raw merge keys in the narrative.
- Do not suggest immediate ranging removal without flagging this should go through the buying team.
- Do not conflate REPEAT_REQUEST (an ordering/demand problem) with EXCESSIVE_OVERRIDE (a compliance/training problem) — the recommended actions are different.
