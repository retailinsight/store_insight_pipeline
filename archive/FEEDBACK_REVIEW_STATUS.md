# StoreInsight General Feedback — Review Status

**Source:** `store_insight_general_feedback_summary_Bryan.md` (reviewed against `main`/pre-merge state).  
**Reviewed branch:** `feat/ukcoop-env-scaling-merge` (current working branch, post-merge).  
**Date:** 2026-08-03  
**Status:** local draft — not committed.

---

## Executive summary

The feedback summary raised three themes:

1. `MARKDOWN_SKU` crowding out other alert types after `top_n_per_store`.
2. Cost framing being unclear or inconsistent (especially `COMPLIANCE` / `TICK_AND_FLICK`).
3. Alert taxonomy and root-cause clarity (markdown/compliance/waste/OSA).

After reviewing the current merged branch, **the underlying code infrastructure exists for several items, but the immediate configuration and narrative guardrails are still missing**. Most of the remaining work is product/PRD decisions, data-source changes, or config tuning rather than raw code gaps.

---

## 1. Done — implemented in current branch

| # | Feedback item | Where it is in the branch | Notes |
|---|---|---|---|
| 1.1 | Variety constraint (`max_per_type_per_store`) infrastructure | `pipeline/config/models.py` (`OutputConfig.max_per_type_per_store`), `pipeline/stages/_2_score/score.py` (`apply_top_n_filter`), `pipeline/pipeline/pipeline.py` line 845 | Code is fully wired. The constraint is read from config and enforced after scoring. |
| 1.2 | SKU-level markdown detectors | `pipeline/stages/_1_detect/detectors/markdown_sku/repeat_request.py` and `excessive_override.py`, registered in `pipeline/config/base/default.yaml` | Both detectors exist and are wired into the registry. |
| 1.3 | `TICK_AND_FLICK` cost computation | `pipeline/stages/_2_score/scorers/compliance.py` | Computes real `projected_cost` as `SUM(LOST_SALES_VALUE)` of tick-and-flicked `(STORE_ID, ITEM_CODE, DATE)` tuples joined to OSA. |
| 1.4 | Waste STB data-quality limitation acknowledged | `pipeline/stages/_1_detect/detectors/waste/vs_chain.py` docstring, `pipeline/docs/semantic_model.md` | Documents that `FINAL_PRICE` is NULL for 100% of EoE rows, so the pipeline uses `WASTE_QTY / QTY_MARKDOWN` as a proxy. |
| 1.5 | Region/area columns on store hierarchy | `pipeline/contracts/wmd_store_hierarchy_v1.yaml` | Optional `REGION` and `AREA_NUMBER` columns exist in the contract. |

---

## 2. Not done / still open

| # | Feedback item | Current state in branch | What remains |
|---|---|---|---|
| 2.1 | Set `max_per_type_per_store` for `eastofengland` | **DONE 2026-08-21** on `feat/alert-cap-max-per-type` (`e3ac879`): cap = 2 (Dan's number), plus Dan's let-out in `apply_top_n_filter` (break the cap rather than send fewer than top_n). | PR review by Dan; record before/after alert mix in `RISK_VALIDATION.md` after deploy. |
| 2.2 | `TICK_AND_FLICK` narrative inconsistency | **DONE 2026-08-21** on the same branch: skill doc now describes the measured LSV cost (with £0 fallback) instead of the false "no £ projection" claim. | PR review by Dan. |
| 2.3 | `MARKDOWN_OVERRIDE` direction (higher vs lower) | `pipeline/contracts/markdown_log_v1.yaml` only has `IS_OVERRIDDEN` and `MARKDOWN_PERCENTAGE` (actual % applied). No `RECOMMENDED_MARKDOWN_PERCENTAGE` or `RECOMMENDED_PRICE`. | Need a new contract field and detector logic to compare actual vs recommended markdown. This is a data-source/PRD change. |
| 2.4 | `MARKDOWN_OVERRIDE` 5% score weight rationale | `pipeline/config/base/default.yaml` has `scoring.score_weights.MARKDOWN_OVERRIDE: 0.05` with no ADR or calibration doc. | Document or calibrate the multiplier. Suggested first step: sensitivity test (3% / 5% / 10%) to see if ranking materially changes. |
| 2.5 | `MARKDOWN_SKU` same-day / intra-week gaming detector | `repeat_request.py` requires `DISTINCT_MARKDOWN_WEEKS >= 3`, so same-day bursts are invisible. `excessive_override.py` measures 4-week override rate, not intra-week clustering. | Build a net-new detector that flags N+ requests for the same store-SKU within a single day or rolling 48–72h window. |
| 2.6 | Distinguish gaming `REPEAT_REQUEST` from genuine chronic slow-seller | `repeat_request.py` does not expose an intra-week request-clustering fact. | Add a fact such as `max_requests_in_single_day` to the signal to help narratives/Action classify the root cause. |
| 2.7 | OSA region / area / cluster drift | `osa_chain_drift.py` only compares store vs full chain. `osa_v1.yaml` has no region/area/cluster columns. No OSA gatherer joins `wmd_store_hierarchy`. | Add store-hierarchy join for OSA and a region/area drift gatherer to support escalation vs store-action decisions. |
| 2.8 | Waste cost as STB-only (where data allows) | `waste.py` scorer uses `this_week_waste_value` for all waste. No `is_markdown`-equivalent flag in the wastage contract. | Need per-client data: which clients have a usable `is_markdown`/`FINAL_PRICE` flag? For those clients, split waste cost into STB vs markdown-waste. |
| 2.9 | "Maximum cost" narrative guardrails | No skill-level or config-level "maximum cost" pattern exists. | Define a narrative pattern that communicates real computed figures as an honest ceiling without agent exaggeration. Apply first to `TICK_AND_FLICK`, then to `WASTE` and others. |
| 2.10 | Controllability / escalation tags | No classification of alerts as store-controllable, escalation, or informational. | Add a controllability tag to alerts (e.g., in `_build_card` or as a config-driven signal-type bucket label). |
| 2.11 | Two explicit cost concepts (recurring vs this-week urgent) | `projected_cost` is a single field per signal. | Define and implement `recurring_cost` and `this_week_urgent_cost` fields, with narrative rules for when to use each. |

---

## 3. Suggested priority order

### Immediate (low risk, high impact)

1. **Set `max_per_type_per_store`** in `pipeline/config/clients/eastofengland/client.yaml`.
2. **Fix `compliance_investigation_skill.md`** to remove the inaccurate "no £ projection" claim and frame the LSV as a measured "at risk" / maximum cost.

### Short-term (needs PRD or data-source change)

3. Add `RECOMMENDED_MARKDOWN_PERCENTAGE`/`RECOMMENDED_PRICE` to `markdown_log` contract and split `MARKDOWN_OVERRIDE` by direction.
4. Build same-day / intra-week burst detector for `MARKDOWN_SKU`.
5. Add region/area/cluster drift gatherer for OSA.
6. Confirm which clients have a usable `is_markdown`/`FINAL_PRICE` waste flag and implement STB-only cost where possible.

### Longer-term (product/UX)

7. Document or calibrate `MARKDOWN_OVERRIDE` 5% weight.
8. Implement "maximum cost" narrative guardrails across skill docs.
9. Add controllability / escalation tags to alert cards.
10. Split `projected_cost` into recurring and this-week urgent cost fields.

---

## 4. Cross-reference to merge notes

- `MERGE_TRACKING.md` records the merge state and validation.
- `RISK_VALIDATION.md` should be updated after any of the above config changes are deployed, because they affect live alert mix and business interpretation.
