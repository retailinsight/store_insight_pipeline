# StoreInsight General Feedback Summary

> **Purpose:** Capture test observations and product feedback so they can be picked up by future PRDs and roadmaps.  
> **Scope:** Excludes the `MARKDOWN_SELLTHROUGH` cost/value bug, which is already documented in the recent ADR/PRD files.  
> **Status:** Raw observations — not yet a PRD or decision record.

---

## 1. Executive Summary

Recent testing surfaced three broad themes for StoreInsight:

1. **Alert-type crowding** — `MARKDOWN_SKU` makes up 92.8% (1,034/1,114) of *delivered* alerts (after the `top_n_per_store` cap), not raw store penetration. The primary cause is an existing but unconfigured safeguard (`max_per_type_per_store`), with detection-threshold tuning as a secondary, independent follow-up.
2. **Cost framing** — Several alerts report a projected cost, but the business interpretation of that cost is unclear or inconsistent (maximum cost, ignored revenue, controllable vs. uncontrollable waste, etc.). One concrete inconsistency was found: `COMPLIANCE`/`TICK_AND_FLICK` computes a real cost internally but the narrative layer's guidance incorrectly claims none exists.
3. **Alert taxonomy and root-cause clarity** — A number of markdown and compliance alerts blend several distinct underlying behaviors (gaming, process errors, ordering issues) or are missing detectors for behaviors they're assumed to cover (e.g. same-day gaming under `MARKDOWN_SKU`). Untangling them will improve actionability and reduce false positives.

These observations are grouped below by functional area, with open questions and suggested directions for future PRDs.

---

## 2. Alert Thresholds and Prioritization

### Observation: `MARKDOWN_SKU` is crowding out every other alert type
- **Corrected metric:** 1,034 / 1,114 (92.8%) is **not** store penetration — it's the signal-type breakdown of the **final selected alert pool after the `top_n_per_store=10` cap**, per `qc/pipeline_run_qc.ipynb` (`top_n_per_store=10: 3113 → 1114 signals to enrich`, then `MARKDOWN_SKU=1034` of the 1114 that made the cut). The other four signal types combined (`COMPLIANCE=14, MARKDOWN_OVERRIDE=4, OSA=10, WASTE=52`) make up only ~7% of what's actually delivered.
- **Root cause #1 — an existing safeguard is unconfigured, not missing.** The codebase already has a `max_per_type_per_store` **Variety Constraint** built for exactly this problem (`config/models.py OutputConfig.max_per_type_per_store`, wired into `pipeline.py`'s `apply_top_n_filter`, documented in ADR 0001 and `CONTEXT.md`). It defaults to `0` ("no constraint") and is **not set** in `config/base/default.yaml` or `config/clients/eastofengland/client.yaml` — only the overall `top_n_per_store: 10` is set. Because `MARKDOWN_SKU` fires **per store-SKU pair** while `OSA`/`COMPLIANCE`/`WASTE`/`MARKDOWN_OVERRIDE` fire per store-department or per store, a store can have dozens of qualifying SKUs but usually only a handful of qualifying departments — so without a per-type cap, `MARKDOWN_SKU` structurally wins nearly every ranked slot.
- **Root cause #2 — detection thresholds may still be too loose independently.** Even with `max_per_type_per_store` enabled, the quota reserved for `MARKDOWN_SKU` could still fill with low-value/low-severity SKU alerts if the underlying detector thresholds (`min_markdown_weeks=3`, `min_markdown_requests=8`, `min_sku_override_rate=0.90`) let through too many marginal cases. These two root causes are independent and both need addressing.
- **Suggested direction for PRD:**
  - **Immediate:** set `max_per_type_per_store` for `eastofengland` (and audit other clients for the same gap) so no single signal type can monopolize the top-N per store.
  - **Follow-up:** after the variety constraint is in place, re-measure the *rate* of `MARKDOWN_SKU` signals per qualifying SKU (not per store) to judge whether the per-SKU thresholds themselves are too loose, and tune independently of the variety-constraint fix.
  - Consider segmenting by store format, category, or markdown depth once the above are resolved.
  - Evaluate whether `MARKDOWN_SKU` should remain a standalone alert or be absorbed into a compliance family (see 6.2 below).

### Theme: Balance recurring, major issues against short-term urgent issues
- Current alerts may mix two lenses:
  - **Structural/recurring cost lens:** “We consistently lose X to markdowns / OSA / waste every week.”
  - **Short-term urgency lens:** “This specific issue is costly *right now* and needs immediate attention.”
- **Suggested direction for PRD:**
  - Define two explicit cost concepts for ranking alerts:
    1. **Overall recurring cost / trend** — e.g., trailing 4-week average cost for the alert family.
    2. **Cost this week / projected incremental cost** — the additional cost expected if the issue is not acted on immediately.
  - Expose both in the narrative so users can triage by either lens.

---

## 3. On-Shelf Availability (OSA)

### `osa_chain_drift`
- **Current behavior:** `stages/_3_facts/gatherers/osa_chain_drift.py` compares a store's WoW OSA drift for a department against the **chain-wide** WoW drift for that same department, to contextualize whether a store's drop is store-specific or a market-wide pattern.
- **Gap:** OSA has no grouping level between "single store" and "whole chain." Checked `contracts/osa_v1.yaml` — it only carries `STORE_ID` (plus item-level hierarchy); there is no `REGION`/`AREA`/`CLUSTER` column, and no OSA detector or gatherer joins to a store hierarchy at all (unlike the WMD/markdown side, where `wmd_store_hierarchy_v1` already has unused `REGION`/`AREA_NUMBER` fields — see `MARKDOWN_SKU`/`MARKDOWN_OVERRIDE` review above).
- **Suggested direction for PRD:**
  - Add (or extend) a store hierarchy contract for the OSA pipeline — joined the same way `wmd_store_hierarchy` is joined on the markdown/waste side — to expose `REGION`/`AREA`/`CLUSTER`.
  - Add a **division / store-cluster drift** variant of `osa_chain_drift` (average WoW drift for the store's region/cluster, not just the full chain) as a third comparison point between store-level and chain-level.
  - Business value: helps a central team decide if the issue is store-controllable (e.g., local replenishment failure) or requires escalation to supply chain / merchandising / operations — a store that's dragging down its whole cluster points one direction, a store that's an outlier even within a struggling cluster points another.

---

## 4. Compliance

### 4.1 Tick-and-flick dismissals
- **Observation:** Alerts are sometimes dismissed with minimal justification ("tick and flick"). The dismissed alerts can still represent lost sales value (LSV) or real cost.
- **Found a real inconsistency between scoring and narrative today:**
  - `stages/_2_score/scorers/compliance.py` **does** compute a genuine, non-invented `projected_cost` for `TICK_AND_FLICK`: `SUM(LOST_SALES_VALUE)` of the exact items behind this store's tick-and-flicked alerts this week, joined on `(STORE_ID, ITEM_CODE, DATE)` to real OSA data. This drives Financial Severity/ranking.
  - `stages/_4_investigate/skills/compliance_investigation_skill.md` says the opposite — *"No £ projection is available for compliance signals... Do not invent a £ projection... Do not attempt to calculate or fabricate a £ figure"* — and mandates a fixed qualitative sentence with no numbers in the narrative. This instruction is factually wrong about *why* (a real cost is computed; it's being deliberately withheld, not because it doesn't exist) — the skill doc should at minimum be corrected to reflect that reasoning accurately.
- **Direction (open, business call, not fully resolved here):** we don't want the agent to hallucinate a cost or have the narrative exaggerate an uncertain figure. But since the LSV figure is genuinely measured (not invented), it should be usable as a **"maximum cost"** framing to drive urgency and inform "cost per day" / severity ranking, without claiming it as a certain realized loss. This distinguishes "communicating impact honestly using a real number" from "inventing or exaggerating a number."
- **Suggested direction for PRD:**
  - Correct the skill doc's inaccurate "no £ projection is available" claim regardless of the final narrative decision.
  - Define a "maximum cost" narrative pattern usable here and elsewhere (see 7.1 cross-cutting theme): state the real computed LSV as an upper-bound/"at risk" figure tied to dismissed alerts, distinct from a certain realized loss — and use it consistently for severity/urgency signaling (e.g. cost-per-day) without adding agent-generated commentary that could exaggerate it.
  - Apply the same guardrail pattern (real number, honestly framed as a ceiling) to other signal types facing the same certain-vs-potential cost ambiguity.

### 4.2 `MARKDOWN_OVERRIDE`
- **Taxonomy question:** Should this be classified as a compliance issue rather than a pricing/markdown issue?
  - Overrides are often associated with gaming or policy violations.
- **Direction of impact is ambiguous:**
  - Current framing appears to assume a *higher* price override.
  - At Kroger, anecdotally the problem is usually a *lower* override (driving price down to avoid repeat markdowns).
  - Same pattern appears in multiple repeat scans and other gaming behaviors.
  - **Contract gap:** direction is not derivable from existing data. `markdown_log_v1` only has `IS_OVERRIDDEN` (boolean) and `MARKDOWN_PERCENTAGE` (the single % actually applied, not paired with a recommended %); `ORIGINAL_PRICE` is optional and unused by the detector. To split by direction we need a new field — e.g. `RECOMMENDED_MARKDOWN_PERCENTAGE` or `RECOMMENDED_PRICE` — added to the contract so actual vs. recommended can be compared per event.
- **Cost-calculation questions:**
  - `projected_cost = this_week_overrides × avg_£_per_markdown_event`, then scaled by `scoring.score_weights.MARKDOWN_OVERRIDE = 0.05` (`pipeline/config/base/default.yaml`) — i.e. only 5% of the gross override value is treated as "at risk."
  - **Open question: how was this 5% figure originally derived?** It is a hardcoded config default with no documented rationale, calibration data, or ADR behind it — ask whoever set it before treating it as authoritative.
  - We do want to eventually replace this flat 5% with an actual sell-through-impact estimate (some items may still sell at the higher, non-overridden price). However, we should not invest in a full modeling effort until we've confirmed it would meaningfully change ranking or recommended actions — if the practical impact of a better estimate is small, a documented/calibrated constant may be good enough.
- **Suggested direction for PRD:**
  - Split `MARKDOWN_OVERRIDE` into sub-types by direction of override and intent:
    - Higher override (legitimate price correction, policy breach, or margin risk)
    - Lower override / gaming (repeat scans, manager attempts to drive price below approved level)
  - Before modeling sell-through impact, run a lightweight sensitivity check: how much would ranking/actions change if the multiplier were, say, 3% vs. 5% vs. 10%, or replaced with a rough sell-through-based estimate? Only invest in a full model if that check shows material impact.
  - Consider merging lower-override patterns with other gaming-related alerts.

---

## 5. Waste

### 5.1 `STB` ("Straight-To-Bin") calculation
- **Correction:** `STB` = **Straight-To-Bin** (waste disposed of directly, never marked down first) — not "sell-through before."
- **This is already a documented, resolved data-quality finding for East of England, not an open question.** Per `docs/semantic_model.md` (confirmed 2026-04-09): the source `FINAL_PRICE` column was intended to be NULL exactly when an item was disposed straight-to-bin (i.e. the `is_markdown`-equivalent flag) — but it is NULL for **100% of EoE rows** (11,084 rows checked). `WASTE_REASON` values (`OUT OF DATE`, `DAMAGED`, etc.) describe *why* an item was wasted, not *whether* it went through markdown first, so they can't substitute. The team's adopted fallback is `WASTE_RATE = WASTE_QTY / SUM(QTY_MARKDOWN)` — a normalized "waste per unit put through markdown" rate that does **not** distinguish STB from markdown waste (see `stages/_1_detect/detectors/waste/vs_chain.py` docstring for the same reasoning restated at the code level).
- **Alternative data source:** At Kroger and other clients, waste records reportedly include a usable `is_markdown` (or equivalent) flag. This is a **per-client data-availability question**, not a pipeline design gap — the pipeline already has the correct target metric in mind (STB vs. markdown waste), it's specifically EoE's source data that can't support it.
- **Confidence issue:** Waste data quality depends on processes that are easy to skip (e.g., staff throwing out expired/damaged goods without recording it), independent of the STB/markdown distinction.
- **Suggested direction for PRD:**
  - Escalate to clients whose `FINAL_PRICE`/`is_markdown`-equivalent field is unpopulated (e.g. EoE) to fix data capture at the source, rather than permanently engineering around it — the proxy metric is a known, accepted limitation, not a target state.
  - For clients where the flag *is* populated (e.g. Kroger), use it directly instead of the `WASTE_QTY / QTY_MARKDOWN` proxy; make this a per-client capability rather than assuming one metric fits all clients.
  - Build/monitor confidence in waste recording accuracy generally before treating waste cost as a primary driver of alert ranking.

### 5.2 What cost should waste alerts represent?
- **Observation:** Our cost should arguably be **STB (straight-to-bin) / non-markdown waste only**.
  - Markdown waste is assumed to have gone through the proper markdown process; some portion may simply be unsellable.
  - Little can be done after the fact.
- **Framing:** If a cost is shown, it should be a **maximum cost** because some items would not have sold even at markdown.
- **Dependency:** this requires resolving 5.1 first — today's `WASTE_QTY / QTY_MARKDOWN` proxy cannot isolate STB waste from markdown waste at all for clients like EoE, so this cost redefinition is only implementable where a real STB/`is_markdown` flag exists.
- **Suggested direction for PRD:**
  - Where the flag is available, define waste alert cost as non-markdown (STB) waste cost only.
  - Report markdown waste separately as an informational metric or maximum cost, not as a primary action driver.

---

## 6. Markdown Alerts

> Note: the `MARKDOWN_SELLTHROUGH` cost/value bug is intentionally omitted here; it is covered in the recent ADR/PRD files.

### 6.1 `MARKDOWN_SELLTHRU` root-cause clarity — mostly already addressed by design
- **Observation:** One listed root cause is *"Product-market fit: Items don't appeal to this store's customer base, regardless of price"* — initially flagged as a concern since this is likely not store-controllable.
- **On inspection, the design already guards against this well:** per `stages/_4_investigate/skills/markdown_sellthrough_investigation_skill.md`:
  - Product-market fit is listed only as one of three prompts for the narrative to *investigate*, not a prescribed conclusion — *"the narrative should prompt investigation of which cause applies, not prescribe the answer."*
  - The actual **Recommended Action** templates never surface a non-controllable action — both prescribed actions (review markdown depth/placement, ensure signage) are store-controllable.
  - There's an explicit existing guardrail: *"Do not assume poor sell-through is always the store's fault — some products may have genuine demand issues at chain level."*
- **Suggested direction for PRD:** treat this as a verification item rather than an open design gap — spot-check real generated narratives (via QC) to confirm they aren't drifting from this guidance in practice, rather than changing the skill itself.

### 6.2 `MARKDOWN_SKU`
- **Taxonomy question:** Should this fall under compliance rather than markdown?
  - Excessive overrides feel adjacent to `MARKDOWN_OVERRIDE`.
- **Repeat-request behavior conflates/misses two distinct issues.** Checked the actual detector (`detectors/markdown_sku/repeat_request.py`): it fires on `DISTINCT_MARKDOWN_WEEKS >= min_markdown_weeks` (default 3) **AND** `TOTAL_MARKDOWN_REQUESTS >= min_markdown_requests` (default 8) within a 4-week rolling window. The `>= 3 distinct weeks` clause is structural, so this detector **cannot** be the same mechanism covering both patterns:
  1. **Gaming (same-day / short-burst)** — repeated markdown requests concentrated in a single day or a couple of consecutive days, used to drive the price lower / create phantom markdown inventory. This is **structurally invisible today**: any item whose requests stay within 1-2 calendar weeks fails the 3-week gate no matter how many requests pile up. No detector anywhere in the codebase currently looks at same-day/intra-week request clustering. This is a real gap, not a config tweak — flagged as a priority given it's a known issue across multiple clients even with anti-tick-and-flick guardrails in the source pricing system.
  2. **Long-term ordering issue** — the same product is repeatedly marked down over months because of persistent over-ordering, poor ranging, or demand mismatch. This is what `REPEAT_REQUEST` is actually built and documented to detect today.
  - **Secondary gap:** even among items that *do* fire `REPEAT_REQUEST` (3+ distinct weeks), the signal has no field distinguishing "gaming recurring weekly" from "genuine chronic slow-seller" — same signal shape, different root cause and different recommended action.
- **Suggested direction for PRD:**
  - Evaluate whether `MARKDOWN_SKU` and `MARKDOWN_OVERRIDE` should be merged into a single **markdown compliance** family.
  - Build a net-new short-window/intra-week burst detector for same-day gaming (e.g. N+ markdown requests for the same store-SKU within a single day or rolling 48-72h window) — this does not exist today and is not a variant of `REPEAT_REQUEST`.
  - For existing `REPEAT_REQUEST` signals, consider adding an intra-week request-clustering fact (e.g. max requests in any single day within the window) to help distinguish weekly-gaming from genuine chronic ordering issues, rather than renaming/splitting the trigger itself.

---

## 7. Cross-Cutting Themes for Future PRDs

### 7.1 Cost certainty and narrative guardrails
- Many cost figures should probably be framed as **maximum cost**, **potential cost**, or **lost sales value (LSV)** rather than certain loss.
- Future PRDs should define:
  - When a numeric cost may be stated.
  - When it must be suppressed or shown as a range.
  - How to prevent agent narratives from inventing costs.

### 7.2 Controllability framing
- Users need to know whether an issue is:
  - **Store-controllable** (replenishment, local pricing compliance, waste recording)
  - **Requires escalation** (chain-wide OSA drift, central ranging, supplier issue)
  - **Informational only** (product-market fit, markdown waste that has already occurred)
- Future PRDs should add a controllability tag or escalation signal to relevant alerts.

### 7.3 Direction of impact
- For pricing/compliance alerts (`MARKDOWN_OVERRIDE`, repeat requests), the direction and intent of the behavior matters.
- Future PRDs should require sub-typing by direction (higher vs. lower) and intent (legitimate vs. gaming).

---

## 8. Open Questions to Resolve Before Roadmapping

1. What `max_per_type_per_store` value should be set per client, and does any client besides eastofengland have the same unconfigured gap?
2. Once the variety constraint is fixed, what target rate of `MARKDOWN_SKU` signals per qualifying SKU (not per store) is acceptable, and do the per-SKU thresholds (`min_markdown_weeks`, `min_markdown_requests`, `min_sku_override_rate`) need retuning?
3. Do we want two explicit cost fields on every alert: **recurring/trailing cost** and **this-week urgent cost**?
4. Should `MARKDOWN_OVERRIDE` and `MARKDOWN_SKU` (excessive override / repeat request) be merged into one markdown-compliance alert family?
5. Who set the `MARKDOWN_OVERRIDE` 5% (`score_weights`) config value, and on what basis — is it worth calibrating, or is it good enough given the low expected impact on ranking?
6. Which clients have a usable `is_markdown`/straight-to-bin equivalent flag (like the dropped `FINAL_PRICE` for EoE), and can EoE's source system be fixed to populate it?
7. What are the exact guardrails needed for a "maximum cost" narrative pattern (e.g. for `TICK_AND_FLICK`) so it communicates real, measured figures as an honest ceiling without agent-generated exaggeration?
8. Is a net-new same-day/intra-week burst detector for `MARKDOWN_SKU` gaming worth prioritizing given it's reportedly a recurring issue across multiple clients?

---

## 9. Suggested Next Steps

1. **Enable the variety constraint:** Set `max_per_type_per_store` for `eastofengland` (and audit other clients) — this is the immediate, low-risk fix for `MARKDOWN_SKU` crowding.
2. **Threshold review:** After (1), re-measure `MARKDOWN_SKU`'s per-SKU firing rate to judge whether `min_markdown_weeks`/`min_markdown_requests`/`min_sku_override_rate` need retuning independently.
3. **New detector spike:** Scope a same-day/intra-week burst detector for `MARKDOWN_SKU` gaming, since it's structurally impossible for `REPEAT_REQUEST` to cover it today.
4. **Taxonomy workshop:** Decide whether `MARKDOWN_OVERRIDE`, `MARKDOWN_SKU`, and repeat-request behaviors belong in one compliance family.
5. **Cost-definition workshop:** Standardize terminology across alerts (certain cost, maximum cost, LSV, projected cost, recurring cost, this-week cost); resolve the `TICK_AND_FLICK` scoring/narrative inconsistency as a concrete first case.
6. **Data-validation spike:** Confirm which clients (e.g. Kroger) have a usable `is_markdown`/straight-to-bin flag; escalate to clients like EoE where the equivalent field (`FINAL_PRICE`) is unpopulated.
7. **Agent-narrative guardrails:** Draft prompt/template rules for a "maximum cost" pattern using real computed figures honestly, without agent-generated exaggeration.
8. **Controllability tagging:** Prototype an "escalation vs. store action" tag on `osa_chain_drift` and markdown alerts, contingent on adding store hierarchy (region/cluster) to the OSA pipeline.
