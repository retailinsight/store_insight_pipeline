# Smart Action Card — Content Skill

## Purpose
Generate the content for a Smart Action card surface in StoreInsight. Each card represents a single investigated signal for a store manager. Content must be **concise, specific, and commercially grounded** — a manager should be able to read, understand, and act within 30 seconds.

---

## Card Anatomy

The card has five content slots, rendered top to bottom:

---

### 1. Title
**Format:** `[DEPARTMENT]: [One-line issue statement]` 
**Rules:**
- Department name in caps, then a colon
- Issue statement is plain English, not data — it conveys *what is wrong*, not just *what the numbers say*
- Must include the magnitude if it's the lead insight (e.g. "15.8pp below chain average", "£636 lost this week")
- Max ~12 words after the colon

**Good:** `RED TABLE WINES: OSA is 15.8pp below chain average` 
**Avoid:** `RED TABLE WINES availability issue detected` 

---

### 2. Detail box
A lightly bordered inner panel. Contains three sub-elements in order:

**a) Summary sentence** (1–2 lines)
Plain English statement of the core data: what has happened, what the number is, and what it's being compared against.
> *"There has been £636.62 of lost sales in RED TABLE WINES this week. Store OSA this week is 76.6%, vs chain average of 92.4% (15.8pp gap)."*

**b) Root cause contributors** (labelled list, max 3 items)
Label: `BIGGEST LOST SALES CONTRIBUTORS THIS WEEK:` 
Each item: `[SUBCLASS]: £[value] this week (last week £[value], [+/- delta])` 
Purpose: tells the manager *where* to focus — not just that there's a problem but which shelves.

**c) Supporting signal** (labelled list, max 3 items)
A second diagnostic lens — this will vary by trigger type:
- For OSA signals: `BIGGEST WEEK-ON-WEEK INCREASE IN LOST SALES` (surfaces what's deteriorating)
- For replenishment signals: repeat offender items
- For chain comparison signals: worst performing subclasses vs chain
Each item follows the same `[SUBCLASS]: £[value]` format.

**d) Worst day callout** (single line, if available)
> *"Worst day for lost sales this week: Wednesday (£102.58)"*
This grounds the issue in time and helps the manager plan their week.

---

### 3. Recommended Action panel
**Colour:** Green-tinted border and header (matches current UI)
**Header label:** `RECOMMENDED ACTION` 
**Content rules:**
- 2–4 sentences of specific, operational instruction
- Must reference the department by name
- Must include a timing element if relevant (e.g. "before 8am", "before store opens")
- Must include the specific behaviour to change (e.g. "raise replenishment orders", "coach teams not to override quantities")
- Where a day-of-week pattern exists, name it

**Good:** *"Review availability in RED TABLE WINES daily. Ensure replenishment orders are raised before 8am and all gaps on high-velocity lines are filled before the store opens. Pay particular attention on Wednesdays, the worst day for lost sales this week."*
**Avoid:** *"Review availability and replenishment processes."* (too generic — no timing, no specificity)

---

### 4. Cost if Not Fixed panel
**Colour:** Orange/amber-tinted border and header (matches current UI)
**Header label:** `COST IF NOT FIXED` 
**Content rules:**
- Single sentence
- Always includes a projected £ value and a time horizon (default: 4 weeks)
- Framed as a conditional: "If this continues at the same rate..."
- Value is calculated from `this_week_lsv × projection_weeks` 

**Template:** *"If this continues at the same rate, the store could lose approximately £[projection] in the next [N] weeks."*

---

## Tone & Voice

| Do | Avoid |
|---|---|
| Specific numbers with context | Vague quantifiers ("significant", "notable") |
| Plain English cause statements | Technical jargon (OSA score, trigger type names) |
| Operational instructions with timing | Generic "review and investigate" language |
| Manager-level framing (sales, cost, teams) | Data science framing (model outputs, confidence) |

---

## Content Generation Rules for `investigate_with_cortex` 

When calling Cortex to populate this card, the JSON response schema maps directly to the slots above:

```json
{
  "issue": "[DEPARTMENT]: [one-line issue — max 12 words]",
  "explanation": "[summary sentence] + [worst day callout if available]",
  "cost_if_not_fixed": "If this continues at the same rate, the store could lose approximately £X in the next N weeks.",
  "recommended_action": "[2-4 sentences, specific, timed, department-named]"
}
```

The `subclass_contributors` and `repeat_item_history` facts are rendered directly from structured data — they do not go through the LLM. This keeps those lists accurate and avoids hallucinated figures.

---

## Fallback Rule

If Cortex returns `None`, the rule-based fallback must still populate all five slots. The action and cost fields use templated strings. The detail box renders from raw `facts` dict. The title defaults to `[DEPARTMENT]: £[lsv] lost sales this week`.
