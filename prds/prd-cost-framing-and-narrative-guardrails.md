# PRD — Cost Framing and Narrative Guardrails

**Date:** 2026-08-11  
**Status:** Ready for implementation  
**Related ADR:** ADR 0001 — Composite Score for Alert Ranking (`pipeline/docs/adr/0001-composite-score.md`)  
**Triage label:** `ready-for-agent`

---

## Problem Statement

Store Insight alerts surface a single `projected_cost` figure that is used for two very different jobs: ranking alerts in the composite score and explaining the financial stakes to a store manager in the narrative. The business meaning of that figure is not consistent across signal types, and the narrative layer has no explicit rules for how honestly to frame it.

This creates three concrete problems:

1. **The same number means different things.** For some signals `projected_cost` is a measured ceiling (e.g. the LSV of dismissed availability alerts). For others it is an already-incurred loss. For others it is a forward projection. Ranking them together implies they are comparable, but the narrative cannot treat them identically.
2. **The `TICK_AND_FLICK` skill doc is factually wrong.** `pipeline/stages/_2_score/scorers/compliance.py` computes a real, measured `projected_cost` for `COMPLIANCE`/`TICK_AND_FLICK` signals from the LSV of dismissed availability alerts, but `pipeline/stages/_4_investigate/skills/compliance_investigation_skill.md` tells the narrative engine that *"No £ projection is available for compliance signals"* and forbids any £ figure. The number exists; the skill should not pretend it does not.
3. **Agents can "hallucinate" a cost interpretation.** Without explicit framing tags, the narrative engine has no guidance on whether a cost is certain, a ceiling, recurring, or acute, and no guardrail against inventing a more dramatic number than the signal carries.

---

## Solution

Decompose the single `projected_cost` concept into two independent semantic axes — **Cost Certainty** and **Cost Duration** — and make those axes first-class signal metadata. Add narrative guardrails that require every £ mention to be tied to a real, measured field and framed according to its certainty/duration class.

This PRD does **not** change how `projected_cost` is computed for ranking in v1. It adds metadata and narrative rules so that the same number is communicated honestly.

### Cost Certainty axis

Describes how confident the pipeline is that the £ figure represents money that can actually be recovered or has actually been lost:

- **Realized Cost** — a loss that has already occurred and is not recoverable (rare; most signals do not have this).
- **Ceiling Cost** — an honest upper bound computed from real, measured data, but whose full recoverability is uncertain if the issue is fixed.

### Cost Duration axis

Describes the time horizon of the cost, independent of certainty:

- **Recurring Cost** — a structural, trailing-average weekly cost for the alert family (chronic, ongoing).
- **Acute Cost** — the incremental cost expected specifically if this week's issue is not acted on immediately.

### Narrative guardrails

- Every £ figure in a narrative must be sourced to a named signal field.
- The narrative must use the framing phrase mandated by the signal's `cost_certainty`/`cost_duration` tags (e.g. "up to £X at risk", "£X recurring weekly cost", "£X already lost this week").
- A signal whose `cost_certainty` is Ceiling must never be described as a certain, recoverable loss.
- `TICK_AND_FLICK` specifically must be corrected to state the measured dismissed-alert LSV as a ceiling, not suppress it.

---

## User Stories

1. As a **store manager reading an alert**, I want the narrative to tell me whether a £ figure is a measured ceiling or a certain loss, so that I do not over-react to an upper-bound number.
2. As a **store manager**, I want to know whether an alert's cost is a chronic weekly drain or a one-off spike, so that I can prioritise my team's time correctly.
3. As a **data scientist**, I want every signal to carry explicit `cost_certainty` and `cost_duration` tags, so that downstream consumers do not have to infer semantics from `signal_type`.
4. As a **pipeline operator**, I want the default cost framing for each signal type to be documented and configurable, so that I can adjust it per client without changing code.
5. As a **narrative engineer**, I want the skill docs to specify exact phrases for each cost class, so that rule-based generation produces consistent, honest language.
6. As a **compliance analyst**, I want the `TICK_AND_FLICK` skill to acknowledge the real dismissed-alert LSV as a "maximum cost" ceiling, so that the scoring/narrative inconsistency is removed.
7. As a **product manager**, I want the UI to display both the raw `projected_cost` and its certainty/duration badges, so that users can triage by financial meaning as well as magnitude.
8. As a **QA engineer**, I want narrative tests to fail if a ceiling cost is described as a certain recovered value, so that agent-generated exaggeration cannot slip through.
9. As a **pipeline developer**, I want the cost framing metadata added to the signal dict without changing the output table schema in v1, so that the change is low-risk and backward-compatible.
10. As a **client success manager**, I want to be able to override the default `cost_certainty`/`cost_duration` mapping per signal type in `client.yaml`, so that client-specific data quirks do not require a code release.
11. As a **data scientist**, I want the composite score to keep using `projected_cost` as its financial-severity input while the semantic axes mature, so that ranking stability is not disturbed by this PRD.
12. As a **stage-4 skill author**, I want a single shared "maximum cost" phrase template that can be reused across `TICK_AND_FLICK`, `WASTE_TRIM`, and other ceiling-cost signals, so that wording stays consistent.

---

## Implementation Decisions

### 1. New signal-level fields: `cost_certainty` and `cost_duration`

Each signal dict will carry two optional string tags:

```text
signal['cost_certainty']  # 'realized' | 'ceiling'
signal['cost_duration']   # 'recurring' | 'acute'
```

These tags are metadata, not score inputs in v1. They flow through the pipeline in `SIGNAL_JSON` and are available to the narrative stage. They do **not** require a new output-table column because they live inside `SIGNAL_JSON`.

Default mapping by signal type (overridable via config):

| Signal type | Default `cost_certainty` | Default `cost_duration` | Rationale |
|---|---|---|---|
| `OSA` | `ceiling` | `recurring` | LSV is a forward-looking sales-loss estimate; patterns are usually chronic. |
| `OSA_RECURRING_SLOT` | `ceiling` | `recurring` | Same as OSA; explicitly a recurring slot pattern. |
| `COMPLIANCE` / `AVAILABILITY_TICK_AND_FLICK` | `ceiling` | `acute` | Dismissed-alert LSV is a real measured upper bound for this week's dismissals. |
| `MARKDOWN_OVERRIDE` | `ceiling` | `acute` | Override impact depends on whether the override was correct; measured this week. |
| `MARKDOWN_SELLTHROUGH` | `ceiling` | `acute` | Unsold markdown pool is at risk, not certain loss, and tied to this week's pool. |
| `MARKDOWN_SKU` | `ceiling` | `recurring` | Repeat/override patterns point to a chronic ordering/pricing issue. |
| `WASTE` | `realized` | `acute` | Waste has already been incurred this week. |
| `WASTE_TRIM` | `ceiling` | `acute` | Discount amount is an upper bound on the margin that could have been earned this week. |

### 2. New scorer responsibility: stamp cost framing tags

Every scorer module will set `cost_certainty` and `cost_duration` on the signal after computing `projected_cost`. A shared helper in `stages/_2_score/` will apply the default mapping from config and allow signal-specific overrides.

If a scorer already knows its signal is different from the default (e.g. a `WASTE` scorer that can separate STB vs markdown waste), it may override the tag.

### 3. Config extension: `cost_framing`

Add a new optional `cost_framing` block to `PipelineConfig` (and `default.yaml`):

```yaml
scoring:
  cost_framing:
    defaults:
      cost_certainty: ceiling
      cost_duration: recurring
    by_signal_type:
      WASTE:
        cost_certainty: realized
        cost_duration: acute
      COMPLIANCE:
        cost_certainty: ceiling
        cost_duration: acute
```

Validation ensures only `realized`/`ceiling` and `recurring`/`acute` are accepted.

### 4. Narrative guardrails in skill docs

Introduce a shared "Cost framing" appendix in `stages/_4_investigate/skills/` and reference it from each rule-based skill. The appendix will mandate:

- **Ceiling + Recurring**: "Up to £{projected_cost} recurring weekly cost"
- **Ceiling + Acute**: "Up to £{projected_cost} at risk this week"
- **Realized + Acute**: "£{projected_cost} already lost this week"
- **Realized + Recurring**: "£{projected_cost} average weekly realized cost"

A signal may carry a more specific field name in the narrative (e.g. "dismissed alert LSV" for `TICK_AND_FLICK`) as long as the phrase template is preserved.

### 5. Correct the `TICK_AND_FLICK` skill doc

Update `compliance_investigation_skill.md`:

- Remove the sentence: *"No £ projection is available for compliance signals — do not invent one."*
- Replace the "Cost if Not Fixed" slot guidance with: use the signal's `projected_cost`, framed as a ceiling acute cost: *"Up to £{projected_cost} of dismissed availability alerts this week — a maximum cost ceiling, not a certain loss."*
- Keep the instruction that the agent must not invent numbers not present in the signal fields.

### 6. No output-table schema change in v1

`projected_cost` remains the single numeric cost column on the alert card. `cost_certainty` and `cost_duration` live in `SIGNAL_JSON`. A future PRD can decide whether to promote them to columns.

### 7. UI/consumer guidance

Add a "How to read Store Insight costs" note to `pipeline/docs/insight-impact-measurement-overview.md` (or a new consumer doc) explaining the two axes and the default mapping. This is documentation only; no UI code changes in this PRD.

---

## Testing Decisions

### What makes a good test

Tests should verify the **external behaviour**: the tags stamped on the signal and the phrases generated by the narrative engine. They should not test the internal helper function in isolation unless that function is the simplest boundary.

### Modules to test

1. **Score helpers / default mapping** — unit test that each signal type receives the expected default tags and that per-client config overrides take precedence.
2. **Each scorer** — assert that after scoring a representative signal, `cost_certainty` and `cost_duration` are present and valid.
3. **`compliance_investigation_skill.md` rendering** — parse the updated skill doc and assert that the false "no £ projection" sentence is gone and a ceiling-cost phrase is present.
4. **Narrative generation pipeline** — with a deterministic mock LLM or rule-based renderer, assert that a `COMPLIANCE` signal with `projected_cost=500` produces a phrase containing "up to £500" and does not contain "certain" or "recovered".
5. **Config validation** — `PipelineConfig` rejects invalid certainty/duration values.

### Prior art

- `stages/_2_score/test_score.py` already exercises scorer output for each signal type; extend fixtures to assert the new tags.
- Markdown skill docs are text files; a simple read/string-assert test is sufficient.
- Rule-based narrative tests can reuse the pattern used for existing skill-doc-driven tests, if any; otherwise add a lightweight string-based test in `stages/_4_investigate/tests/`.

---

## Out of Scope

- Changing the composite-score formula or replacing `projected_cost` as the financial-severity input.
- Adding a third **Controllability** axis (store-controllable / escalation / informational). That is a related but separate PRD.
- Promoting `cost_certainty`/`cost_duration` to dedicated output-table columns.
- Modelling per-signal-type uncertainty ranges or confidence intervals.
- Rewriting skill docs for non-cost-related signals beyond ensuring they use the shared framing appendix.

---

## Further Notes

- The `WASTE_TRIM` cost accuracy PRD will change how `projected_cost` is computed for that signal; this PRD only changes how it is described. Coordinate so that `WASTE_TRIM` is tagged `ceiling`/`acute` after the cost fix.
- The `COMPLIANCE` rename to `AVAILABILITY_TICK_AND_FLICK` is a planned separate change; this PRD should work with either signal-type name by keeping the mapping consistent with `OutputConfig.signal_type_buckets`.
- Default values are starting points. Once real client data is available, the mapping should be reviewed and adjusted in `client.yaml` rather than code.
