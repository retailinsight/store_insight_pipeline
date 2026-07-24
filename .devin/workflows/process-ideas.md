---
description: Process ideas from the ideas box — triage unimplementable ones with a TODO list, implement actionable ones on a branch with a PR
---

Work through ideas from the ideas box in a loop — process every `status=new` idea back-to-back, then print a final summary.

**Modes:**
- **Default (loop):** process all ideas automatically without pausing between them.
- **Step-by-step:** if the user invokes this workflow with the words "one at a time", "step by step", or "pause between", pause and ask "Continue to the next idea?" after each one.

For each idea:
- Assess whether it is implementable given the current codebase and known data contracts.
- If not implementable: produce a step-by-step TODO list and mark it as triaged.
- If implementable: implement the code on a feature branch and open a PR.

---

## Step 1 — Fetch new ideas

Use the `list_ideas` MCP tool to retrieve all ideas with `status=new`.

If no ideas are returned, tell the user the ideas box is empty and stop.

Print a numbered summary of the ideas found (id, title, category, votes) so the
user can see what is queued.

---

## Step 2 — For each idea (one at a time)

Pick the first unprocessed idea and work through steps 2A–2D.  Repeat for every
idea in the list.

In **step-by-step mode** only: after each idea, report the outcome and ask
**"Continue to the next idea?"** before proceeding.  In default loop mode,
print a one-line outcome (`✓ implemented — PR: <url>` or `→ triaged`) and
move immediately to the next idea.

### 2A — Assess the idea

Read the idea's `title`, `body`, and `category` fields.  Then assess it against
the criteria below.

**Implementable — proceed to 2C** if ALL of the following are true:
- The logic can be expressed entirely in Python using Snowpark DataFrames.
- Any required data is already available in an existing contract (see contracts
  in `pipeline/contracts/*.yaml`) OR is already consumed by an existing
  detector/gatherer even if not yet formalised in a contract.  Data that exists
  in the pipeline but hasn't been used in a particular way is still fine.
- No new Snowflake source tables are needed that have never been referenced in
  the codebase.
- No human product or commercial decisions are required before coding can start.
- The scope fits in a single PR (≤ ~300 lines of new/changed code).

**Not implementable — proceed to 2B** if ANY of the following are true:
- Requires a data source that has never appeared anywhere in the codebase
  (no contract, no adapter SQL, no reference in any loader or detector).
- Requires a cross-cutting architectural change (e.g. new pipeline stage,
  new DB schema, change to the `ALERTS_PIPELINE` output schema).
- Requires a product or commercial decision before coding (e.g. "should we
  charge for this?", "which stores should see this?").
- Requires external integrations not present in the codebase (e.g. email,
  Slack, external APIs).
- Scope is too large for a single PR.

### 2B — Not implementable: produce a TODO list

Produce a numbered, step-by-step TODO list that describes exactly what a
developer needs to do to make this idea implementable in the future.  Be
specific — name the files, contracts, and tables involved where possible.

Template (adapt as needed):

```
TODO for idea #<id>: <title>

1. Identify the source table(s) that contain the required data
   (e.g. "Confirm which Snowflake table holds <X> and document its schema")
2. Write a contract YAML at pipeline/contracts/<name>_v1.yaml
   (columns, grain, joins — see existing contracts for the format)
3. Write an adapter SQL view at pipeline/adapters/<client>/<name>.sql
   (transforms the raw table to the canonical contract shape)
4. Run `python pipeline/tools/deploy_views.py --client <client>` to deploy
5. Add the contract name to PARAM_TO_CONTRACTS in pipeline/pipeline/capabilities.py
6. Write the detector or gatherer module (see skill instructions below)
7. If a new signal type: add TypedDict + factory to pipeline/stages/_1_detect/signals.py
8. Add tests
```

Then call `update_idea_status` MCP tool:
- `idea_id`: the idea's id
- `status`: `"triaged"`
- `resolution_note`: the full TODO list text (as a single string)

Report the outcome to the user.

### 2C — Implementable: determine implementation type

Classify the idea into one of:
- **New detector on an existing signal type** (e.g. new OSA trigger)
- **New signal type** (new alert category with its own detectors + gatherers)
- **New gatherer** (richer facts for an existing signal type)
- **New MCP tool** (new query/tool in `mcp/app/server.py`)
- **Config / threshold change** (tweak to `DetectorConfig` defaults)
- **Other** (UI change, prompt/skill edit, refactor)

Then proceed to 2D.

### 2D — Implement

Create a branch named `idea/<id>-<slug>` where `<slug>` is a lowercase
kebab-case summary of the title (max 40 chars).

```
git checkout -b idea/<id>-<slug>
```

Then implement using the skill instructions below for the relevant type.

After implementing, run `ruff check .` — fix any errors before committing.

Commit with:
```
feat(pipeline): <imperative summary of what was implemented>

Implements idea #<id>: <title>

<one-paragraph description of what was built and why>
```

Push and open a PR:
```
git push -u origin HEAD
gh pr create --title "feat: <title> (idea #<id>)" \
             --body "Implements idea #<id>: <title>\n\n<idea body>\n\n---\nAuto-implemented by the process-ideas workflow." \
             --base main
```

Then call `update_idea_status` MCP tool:
- `idea_id`: the idea's id
- `status`: `"in_progress"`
- `resolution_note`: the PR URL

Report the outcome (PR URL, files changed) to the user.

---

## Skill instructions — New detector on an existing signal type

A detector lives at:
```
pipeline/stages/_1_detect/detectors/<signal_type_folder>/<detector_name>.py
```

The `<signal_type_folder>` must be one of the existing subfolders:
`osa`, `compliance`, `markdown_override`, `markdown_sellthrough`, `markdown_sku`, `waste`.

**The file must contain:**

1. A module-level docstring explaining the detector.

2. A `METADATA` attribute:
```python
from store_insight.pipeline.stages._1_detect.detector_info import DetectorInfo

METADATA = DetectorInfo(
    name        = 'TRIGGER_NAME',        # uppercase, e.g. 'WOW'
    problem     = 'What problem this surfaces.',
    action      = 'What the store team should do.',
    baseline    = 'What the metric is compared against.',
    logic       = 'Plain-English firing conditions.',
    config_keys = ['threshold_param_name'],  # DetectorConfig fields this uses
)
```

3. A `detect(...)` function:
```python
def detect(
    <data_param>,           # Snowpark DataFrame — name must match PARAM_TO_CONTRACTS key
    last_week_start,
    last_week_end,
    this_week_start,
    this_week_end,
    threshold_param=<default>,
    store_id=None,
) -> list[dict]:
    ...
    return signals   # list of signal dicts built with the appropriate make_*_signal() factory
```

**The function parameter name for DataFrames must match one of these keys**
(defined in `pipeline/pipeline/capabilities.py: PARAM_TO_CONTRACTS`):
- `osa` → OSA data
- `feedback` → compliance feedback data
- `markdown_log` → markdown log data
- `markdown_sales` → markdown sales data
- `wastage` → wastage data
- `item_hierarchy` → WMD item hierarchy
- `store_hierarchy` → WMD store hierarchy

**Signal factories** (import from `pipeline/stages/_1_detect/signals.py`):
- OSA: `make_osa_signal(store_id, department, trigger_types, ...)`
- Compliance: `make_compliance_signal(store_id, trigger_types, site_name, ...)`
- Markdown override: `make_markdown_override_signal(store_id, trigger_types, ...)`
- Markdown sell-through: `make_markdown_sellthrough_signal(store_id, trigger_types, ...)`
- Markdown SKU: `make_markdown_sku_signal(store_id, item_id, trigger_types, ...)`
- Waste: `make_waste_signal(store_id, trigger_types, ...)`

**Registration is automatic** — no changes to `registry.py` needed.

---

## Skill instructions — New signal type

A new signal type means a new alert category with its own detectors AND gatherers.

**Files to create/modify:**

1. `pipeline/stages/_1_detect/signals.py` — add a new `TypedDict` and `make_<type>_signal()` factory following the existing pattern.  The `merge_key` must be a tuple starting with the signal type string, e.g. `('MY_TYPE', store_id)`.

2. `pipeline/stages/_1_detect/detectors/<new_type_folder>/` — create the folder with an empty `__init__.py` and at least one detector module (see detector skill instructions above).

3. `pipeline/stages/_2_facts/gatherers/<name>.py` — create at least one gatherer (see gatherer skill instructions below).

4. `pipeline/stages/_2_facts/signal_type_gatherers.yaml` — add an entry for the new signal type:
```yaml
MY_NEW_TYPE:
  - name: my_gatherer_name
    description: "What this gatherer provides."
```

5. If the new signal type needs its own investigation skill, add a skill file under `pipeline/stages/_3_investigate/skills/` following the existing pattern.

---

## Skill instructions — New gatherer

A gatherer lives at:
```
pipeline/stages/_2_facts/gatherers/<gatherer_name>.py
```

**The file must contain:**

1. A `METADATA` attribute:
```python
from store_insight.pipeline.stages._2_facts.config import GathererInfo

METADATA = GathererInfo(
    name         = 'gatherer_name',
    signal_types = ['SIGNAL_TYPE'],
    facts_keys   = ['key1', 'key2'],        # keys this gatherer adds to the facts dict
    description  = 'What facts this gathers.',
)
```

2. A `gather(...)` function that takes the relevant DataFrame(s) and `signals` list,
   and returns a dict of results keyed in a way that `extract_facts` can consume:
```python
def gather(<data_param>, signals, last_week_start, last_week_end,
           this_week_start, this_week_end) -> dict:
    ...
```

3. An `extract_facts(signal, raw_result) -> dict` function that extracts the
   per-signal facts from the batch result returned by `gather`.

**Registration**: after creating the file, add the gatherer to
`pipeline/stages/_2_facts/signal_type_gatherers.yaml` under the relevant signal type.

---

## Skill instructions — New MCP tool

Add a new `@mcp.tool()` decorated function in `mcp/app/server.py` following the
existing pattern.  If the tool queries Snowflake, add the query logic in
`mcp/app/alerts_repo.py`.  If it queries Postgres (ideas, etc.), add it in the
relevant repo module.

---

## Step 3 — After all ideas are processed

Print a summary table:

| Idea # | Title | Outcome |
|--------|-------|---------|
| ...    | ...   | implemented (PR: <url>) / triaged (needs: <one-line summary>) |

Ask the user if they want to push the workflow file itself to GitHub.
