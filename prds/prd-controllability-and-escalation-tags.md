# PRD — Controllability and Escalation Tags

**Date:** 2026-08-11  
**Status:** Ready for implementation  
**Related ADR:** ADR 0001 — Composite Score for Alert Ranking (`pipeline/docs/adr/0001-composite-score.md`) (for Score Dimension extension pattern)  
**Triage label:** `ready-for-agent`

---

## Problem Statement

Store Insight alerts currently mix issues that a store manager can act on locally with issues that need escalation to a central team, supplier, or category manager. Without an explicit classification, every alert is presented with the same "store action" framing. This leads to three problems:

1. **Managers waste time on non-actionable alerts.** An alert driven by a chain-wide OSA drift or a central ranging decision looks like a local problem even though the store cannot fix it.
2. **Escalation opportunities are lost.** Issues that should be aggregated and sent to a regional or central team remain buried in individual store cards.
3. **Ranking does not reflect who can act.** A high-£ alert that only a central team can fix should not necessarily crowd out a lower-£ alert that a store manager can fix today.

`pipeline/CONTEXT.md` records a proposed third cost axis, **Controllability**, independent of Cost Certainty and Cost Duration. This PRD formalises it as a set of tags attached to each signal.

---

## Solution

Introduce a `controllability` tag (or tags) on every signal that classifies who should act on the underlying issue. The v1 classification has three values:

- **`store_controllable`** — the store manager or store team can meaningfully act on the issue. Examples: replenishment, local markdown compliance, local pricing compliance, waste recording discipline, investigating a specific SKU.
- **`requires_escalation`** — the issue is real but the root cause or authority sits outside the store. Examples: chain-wide OSA drift, supplier or DSD failure, central ranging decision, persistent peer-pattern issue that repeats across many stores.
- **`informational`** — the issue has already happened, is not recoverable at the store, or is primarily a data-quality / investigation lead. Examples: markdown waste that has already occurred, `WASTE_TRIM` when retail price is unavailable, some historical pattern alerts.

The tag is derived from a combination of `signal_type`, `trigger_types`, and supporting facts. It is exposed to the narrative stage so the recommended action can say explicitly who should act, and it is considered for ranking as an optional score dimension or post-ranking filter.

In v1 the tag is **display/metadata only**; it does not automatically re-route alerts to a different inbox. That routing is a follow-up workflow feature.

---

## User Stories

1. As a **store manager**, I want to see whether an alert is something I can fix in my store, so that I do not waste time on issues outside my control.
2. As a **store manager**, I want alerts that require escalation to clearly say who they should be escalated to, so that I know the next step.
3. As an **area or regional manager**, I want to see aggregated counts of `requires_escalation` alerts across my stores, so that I can spot systemic issues.
4. As a **pricing analyst**, I want `MARKDOWN_OVERRIDE` and `MARKDOWN_SKU` alerts tagged as store-controllable by default, so that I can focus store conversations on local pricing discipline.
5. As an **operations analyst**, I want `osa_chain_drift` alerts (when the whole chain is moving) tagged as `requires_escalation`, so that they are not treated as a single-store failure.
6. As a **data scientist**, I want the controllability tag to be a first-class signal field derived from rules, not a post-hoc narrative guess, so that it can be used for filtering and ranking.
7. As a **pipeline operator**, I want the default controllability mapping to be configurable per client, so that the same signal type can be tagged differently depending on the client's operating model.
8. As a **product manager**, I want informational-only alerts to be visually distinct, so that users treat them as leads rather than urgent action items.
9. As a **QA engineer**, I want deterministic unit tests for the controllability classifier, so that a change to one signal type does not silently re-tag another.
10. As a **UI designer**, I want a single `controllability` badge per card plus an optional `escalation_target` hint, so that the display is consistent across alert types.
11. As a **composite-score designer**, I want to optionally include controllability as a score dimension in future, so that v1 data collection enables later ranking experiments without changing the v1 ranking formula.
12. As a **narrative engineer**, I want the skill docs to include controllability-specific recommended-action phrasing, so that "escalate to central ranging" and "investigate locally" do not get mixed up.

---

## Implementation Decisions

### 1. New signal field: `controllability`

Each signal dict carries an optional string tag:

```text
signal['controllability']  # 'store_controllable' | 'requires_escalation' | 'informational'
```

Like `cost_certainty`/`cost_duration`, this lives in `SIGNAL_JSON` in v1 and does **not** require a new output-table column. It is available to the narrative stage and to the UI via `SIGNAL_JSON`.

### 2. Default mapping by signal type and trigger type

A shared classifier module applies default rules. Defaults (overridable in config):

| Signal type | Trigger(s) | Default controllability | Rationale |
|---|---|---|---|
| `OSA` | `WOW` (single-store acute drop) | `store_controllable` | Local replenishment/staffing issue. |
| `OSA` | `VS_CHAIN` (below chain) | `requires_escalation` if chain-wide drift fact indicates chain moved; otherwise `store_controllable` | Chain-wide drift is not a single-store failure. |
| `OSA` | `REPEAT` | `store_controllable` | Local chronic availability issue. |
| `OSA_RECURRING_SLOT` | `RECURRING_SLOT` | `store_controllable` if `slot_sales_weeks` is high; `requires_escalation` if pattern spans many stores (peer context unavailable in v1, so default `store_controllable`) | Local delivery/shelf-fill timing issue by default. |
| `COMPLIANCE` / `AVAILABILITY_TICK_AND_FLICK` | `TICK_AND_FLICK` | `store_controllable` | Local alert-working discipline. |
| `MARKDOWN_OVERRIDE` | `WOW` / `VS_CHAIN` | `store_controllable` | Local pricing/override discipline. |
| `MARKDOWN_SELLTHROUGH` | `WOW` / `VS_CHAIN` | `store_controllable` | Local markdown management. |
| `MARKDOWN_SKU` | `REPEAT_REQUEST` / `EXCESSIVE_OVERRIDE` / `BURST` | `store_controllable` | Local SKU-level ordering/pricing behaviour. |
| `WASTE` | `WOW` / `VS_CHAIN` | `store_controllable` (recording discipline) | Store can improve waste recording; root cause may be central ranging. |
| `WASTE_TRIM` | `WASTE_TRIM` | `informational` | Causes are often outside store control; treat as an investigation lead. |

Rules can inspect facts. For example, `OSA` + `VS_CHAIN` + `chain_drift_pp > threshold` -> `requires_escalation`.

### 3. New classifier module

Add a deep module `stages/_2_score/controllability.py` with a single public function:

```text
controllability_tag(signal: dict, cfg: PipelineConfig) -> str
```

The function is pure and deterministic. It reads the signal's `signal_type`, `trigger_types`, and facts, and returns one of the three tags. It does not call Snowflake or perform heavy computation.

The classifier is called in `score.py` after facts are gathered, because some rules depend on fact values (e.g. chain-wide drift indicators).

### 4. Config extension: `controllability`

Add an optional block to `PipelineConfig` (and `default.yaml`):

```yaml
scoring:
  controllability:
    defaults:
      OSA:
        WOW: store_controllable
        VS_CHAIN: requires_escalation
        REPEAT: store_controllable
      # ... other signal types ...
    chain_drift_threshold_pp: 2.0  # example threshold for OSA VS_CHAIN escalation
```

Validation ensures tag values are in the allowed set.

### 5. Narrative skill updates

Each rule-based skill doc should include controllability-aware recommended-action phrasing:

- `store_controllable`: action directed at the store manager ("Investigate", "Review", "Correct").
- `requires_escalation`: action includes escalation target ("Escalate to area manager / central ranging / supplier").
- `informational`: action framed as "Monitor" or "Investigate as a lead".

A shared phrasing appendix in `stages/_4_investigate/skills/` keeps the language consistent.

### 6. Optional score-dimension hook

The classifier writes `controllability` to the signal but does **not** change the composite score in v1. A follow-up PRD can decide whether to add a Controllability score dimension (e.g. prefer `store_controllable` alerts in the top-N) and, if so, how to weight it. The current design keeps the hook ready without altering ranking.

### 7. No automatic routing in v1

The tag is metadata. Any automatic re-routing to a different inbox, dashboard, or owner is out of scope for v1. UI display and narrative phrasing are the only consumers.

### 8. UI/consumer guidance

Add documentation to `pipeline/docs/insight-impact-measurement-overview.md` (or a new consumer doc) explaining the three tags and how downstream consumers should use them. Provide guidance that `informational` alerts should be visually de-emphasised.

---

## Testing Decisions

### What makes a good test

Tests should verify the **external behaviour**: given a signal dict with known type, triggers, and facts, the classifier returns the expected tag. Tests should not depend on the config file location or the narrative engine.

### Modules to test

1. **`controllability.py` classifier** — highest priority. Unit tests for each signal type/trigger/fact combination in the default mapping, plus override tests using a custom config.
2. **`score.py` integration** — assert that after scoring, a representative signal carries a valid `controllability` value.
3. **Config validation** — reject invalid controllability values and unknown signal-type keys gracefully.
4. **Skill docs** — a lightweight text check that `osa_investigation_skill.md`, `waste_trim_investigation_skill.md`, etc. contain controllability-aware phrasing or reference the shared appendix.

### Prior art

- No existing controllability module. The test style can follow `stages/_2_score/test_score.py` with small signal dicts and a `PipelineConfig` fixture.
- Skill docs are plain Markdown; string-assert tests are sufficient.

---

## Out of Scope

- Automatic alert routing / assignment to different teams or inboxes.
- Adding Controllability as an active composite-score dimension in v1.
- Peer-store or region-based controllability rules that require a store-hierarchy join in the OSA pipeline (e.g. `peer_slot_match_rate`).
- Direction/intent subtyping for markdown alerts (higher vs. lower override, legitimate vs. gaming) — blocked on a new contract field.
- Per-client overrides beyond the standard `client.yaml` deep-merge.

---

## Further Notes

- This PRD implements the third axis proposed in `pipeline/CONTEXT.md` (Controllability). It is independent of the Cost Certainty and Cost Duration axes in the Cost Framing PRD, but the three should be documented together in consumer-facing docs.
- `WASTE_TRIM` is intentionally `informational` by default, aligning with the EoE workshop decision that it should not be a strong initial store-facing metric.
- `OSA` + `VS_CHAIN` is the most important escalation case in v1. If the gatherer does not yet expose a clear chain-drift fact, the default for `VS_CHAIN` may be `requires_escalation` until a fact-based rule is added.
- Coordinate with the Outcome Measurement PRD: when a Commitment is `in_progress`, the UI can show both `controllability` and `cost_certainty`/`cost_duration` badges to help managers prioritise which open issues to work on first.
