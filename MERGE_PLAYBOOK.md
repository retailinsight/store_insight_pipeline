# Branch Integration Playbook

**Purpose:** Merge a feature branch into a long-lived environment branch with minimum time, cost, and risk.  
**Written for:** Store Insight style repos (Python pipeline + UI + Snowflake deploy), but the steps are generic.  
**Last updated:** 2026-07-30  
**Status:** local draft — do not commit verbatim; adapt per project.

---

## 1. Principles

- **Never let integration branches live more than a few days.** The longer they diverge, the bigger and more expensive the merge.
- **Pay the conflict cost early and in small chunks.** A one-line conflict now is cheaper than a 500-line conflict later.
- **Validate before you merge, not after.** Run tests, lint, and a conflict preview before touching the merge commit.
- **Treat live systems as read-only until the merge is clean.** Redeploys and backfills are expensive; avoid them by pre-validating schema and deploy scripts.
- **One source of truth per concern.** If two branches edit the same line, decide the canonical version before the merge.

---

## 2. Pre-merge checklist (do this on both source and target branches)

| Step | Command / action | Why |
|---|---|---|
| Sync target | `git fetch origin && git rebase origin/main` (or merge `main` into both branches) | Reduces drift before the integration branch is created. |
| Run tests | `pytest -q` (or project-specific) | Catches failures that are unrelated to the merge. |
| Run lint | `ruff check .` / `ruff format --check` | Avoids style-only conflicts. |
| Scan conflicts without merging | `git merge-tree $(git merge-base HEAD target) HEAD target` | Shows every conflict before you commit anything. |
| Search for stale markers | `grep -R "<<<<<<<\|=======\|>>>>>>>" --include="*.py" --include="*.ts*" --include="*.yaml" --include="*.yml"` | Ensures no leftover markers from previous merges. |
| Review file-level overlap | `git diff --stat target` and `git diff --name-only target` | Tells you which files both sides touched. |

**Rule of thumb:** if the conflict preview shows more than ~10 files, split the merge into smaller parts.

---

## 3. Integration branch workflow

Use a dedicated integration branch, **not** a direct merge into the long-lived environment branch.

```powershell
# 1. Make sure target is up to date
git checkout feat/store-insight-ukcoop-env
git pull origin feat/store-insight-ukcoop-env

# 2. Create integration branch
git checkout -b feat/ukcoop-env-scaling-merge

# 3. Merge the feature branch
git merge feat/pipeline-scaling --no-edit

# 4. If conflicts exist, resolve them incrementally
#    (see conflict-resolution rules below)
```

---

## 4. Conflict-resolution rules

### 4.1 Order of resolution

1. **Tooling/config first** — `.gitignore`, package files, CI workflows, lock files.
2. **Schemas and contracts next** — they dictate what downstream code must produce.
3. **Core logic** — pipeline orchestration, business rules.
4. **UI / API surface** — components, routes, endpoints.
5. **Tests and docs last** — they validate the previous four layers.

### 4.2 How to pick a side

| Situation | Rule |
|---|---|
| One side is a bugfix, the other is a refactor | Take the bugfix. |
| One side adds lineage/audit columns | Keep the lineage columns and update every insert path to populate them. |
| One side renames an internal contract/variable | Adopt the rename and update all call sites in the same commit. |
| Config vs code disagree | Code must match the config file that is actually deployed. |
| UI rewrite vs legacy UI | Port missing features into the new architecture; do not keep both versions. |

### 4.3 Scripted resolution for known conflicts

If the same conflict happens repeatedly, script it instead of resolving it by hand:

```powershell
# Example: ensure a function always returns 27 columns after the merge
python -c "
import re
path = 'pipeline/pipeline/pipeline.py'
text = open(path).read()
text = re.sub(r'old_schema\s*=\s*\[.*?\]', 'new_schema = [...27 items...]', text, flags=re.S)
open(path, 'w').write(text)
"
```

Store these scripts in a scratch folder or in the integration PR description; do not commit throwaway scripts to the target branch.

---

## 5. Validation gates before any commit

Run these in order. Do not move to the next step until the current one is green.

1. **No conflict markers**
   ```powershell
   grep -R "<<<<<<<\|=======\|>>>>>>>" pipeline ui .github
   ```
2. **Clean syntax**
   ```powershell
   python -m compileall pipeline ui scripts
   ```
3. **Tests**
   ```powershell
   pytest pipeline/tests -q
   ```
4. **Lint**
   ```powershell
   ruff check pipeline ui scripts
   ruff format --check pipeline ui scripts
   ```
5. **Deploy dry-run** (if applicable)
   ```powershell
   python pipeline/deploy/deploy.py --client eastofengland --task-off
   ```

---

## 6. Snowflake / live-environment guardrails

Deploys and backfills are the most expensive part of an integration. Minimise them.

| Risk | Prevention |
|---|---|
| Stale deployed zip causes schema mismatch | Always run a deploy dry-run after any change to `_card_to_row`, `_card_schema`, or the output table DDL. |
| Column count mismatch | Add a unit test that asserts the number of tuple items matches the table schema. |
| Silent failures in daily Task | Run `python scripts/check_task_history.py` after deploy. |
| Manual backfills are slow/risky | Fix the root cause before backfilling; never backfill to hide a bug. |
| Live credentials in commits | Never commit `.env`, `snowflake_credentials.py`, or PAT tokens. Use gitignored loaders only. |

**Before deploying:**

```powershell
python -c "from store_insight.pipeline.deploy.handler import run"  # import sanity
python pipeline/deploy/deploy.py --client eastofengland --task-off   # dry-run SP
python scripts/validate_merge_snowflake.py                            # read-only live checks
```

**After deploying:**

```powershell
python scripts/check_task_history.py
python scripts/check_backfill.py
```

---

## 7. Documentation discipline

Keep three documents updated **during** the merge, not after:

| Document | Purpose | Update when |
|---|---|---|
| `MERGE_TRACKING.md` | Step-by-step merge log, conflicts, test results, branch/PR links. | After each batch of resolutions. |
| `RISK_VALIDATION.md` | Active risks, live validation results, incidents, remediation. | After deploy, scheduled run, or incident. |
| `CHANGES_LOG.md` / release notes | What changed, why, and any breaking/user-visible impact. | Before the PR is opened. |

**Do not** copy raw merge logs into Slack or PR bodies. Summarise 3–5 bullets and link to the full file.

---

## 8. Pull-request hygiene

- **PR title:** `feat: merge pipeline-scaling into ukcoop-env`
- **Body template:**
  - What changed (3 bullets)
  - Why it matters (1–2 bullets)
  - Validation performed (tests, Snowflake checks)
  - Active risks / follow-ups
  - Link to `MERGE_TRACKING.md`
- **Commit history:** keep merge commit + resolution commits clean; avoid "fix fix fix" commits by squashing cleanup steps.

---

## 9. Live run observability

Use these commands while a manual backfill or the daily Task is running. They are read-only and safe to run repeatedly.

### 9.1 Backfill progress per analysis date

```powershell
python scripts/check_backfill.py
```

Expected healthy output:

```
analysis_date | cards | distinct_alerts
----------------------------------------
2026-07-22 | 1003 | 998
2026-07-23 | 1056 | 1050
2026-07-24 | 1070 | 1064
2026-07-25 | 1057 | 1051
2026-07-26 | 1018 | 1014
2026-07-27 | 940 | 935
2026-07-28 | 875 | 871
2026-07-29 | 757 | 752

All expected dates have rows.

Duplicate ALERT_IDs per analysis_date (cards > distinct_alerts):
analysis_date | alert_id | count
------------------------------------------------------------
2026-07-22 | 051f0da862701ca9 | 4
2026-07-23 | 8c18eeae0ce87cb8 | 4
... and N more duplicates

Engine mix per analysis_date:
2026-07-22 | rule_based | 1003
2026-07-23 | rule_based | 1056
...
```

What to watch:

- All expected dates show rows before declaring backfill complete.
- `cards` and `distinct_alerts` should be close. If they diverge by more than ~1%, investigate duplicate `ALERT_ID`s.
- `engine_used` should match the intended engine (`rule_based` for scheduled production, `cortex` only for manual comparison runs).

### 9.2 Scheduled Task health

```powershell
python scripts/check_task_history.py
```

Key fields to track:

| Field | Healthy value |
|---|---|
| `STATE` | `SUCCEEDED` |
| `ERROR_MESSAGE` | `NULL` or empty |
| `COMPLETED_TIME` | within a few minutes of `SCHEDULED_TIME` for rule-based runs |
| `DATABASE_NAME` / `SCHEMA_NAME` | `STORE_INSIGHT_DB` / `PUBLIC` |

### 9.3 Quick Snowflake worksheet checks

Run these if you want to verify progress without local Python:

```sql
USE ROLE STORE_INSIGHT_ROLE;
USE WAREHOUSE STORE_INSIGHT_WH;

-- Row count + engine mix per analysis date
SELECT
  analysis_date,
  engine_used,
  COUNT(1) AS cards,
  COUNT(DISTINCT alert_id) AS distinct_alerts
FROM STORE_INSIGHT_DB.PUBLIC.ALERTS_PIPELINE
WHERE analysis_date BETWEEN '2026-07-22' AND CURRENT_DATE()
GROUP BY analysis_date, engine_used
ORDER BY analysis_date, engine_used;

-- Recent task runs
SELECT
  name,
  state,
  scheduled_time,
  completed_time,
  DATEDIFF('second', scheduled_time, completed_time) AS run_seconds,
  error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
  TASK_NAME => 'RUN_ALERTS_PIPELINE_TASK',
  SCHEDULED_TIME_RANGE_START => DATEADD('day', -2, CURRENT_TIMESTAMP)
))
ORDER BY scheduled_time DESC;
```

## 10. Post-merge follow-up

1. Watch the next scheduled run (e.g., daily Task).
2. Compare output row counts and `ALERT_ID` uniqueness against the previous period.
3. Update `RISK_VALIDATION.md` with the first post-merge production result.
4. Close or update any TODOs opened during the merge.

---

## 11. Observing command execution and fixing hangs

During the 2026-07-30 integration, several commands appeared to "hang" or produced confusing output. This section explains why and how to handle it next time.

### 11.1 Why commands looked stuck

| Symptom | Root cause | Fix |
|---|---|---|
| `git add ...; git commit -m "..."; git push ...` never returns | The push step waited for GitHub authentication or an interactive prompt. | Split into separate commands; cache credentials with `git config --global credential.helper manager`. |
| `git commit -m "..."` opened an editor | The shell stripped the double quotes, so Git saw the message as separate arguments and opened `$EDITOR`. | Use single quotes in PowerShell: `git commit -m '...'`. |
| OneDrive sync caused git to pause | Windows file locks / OneDrive upload delayed file writes. | Pause OneDrive sync during heavy git operations; run commands from the local disk if possible. |
| Snowflake backfill command produced no output for minutes | The stored-procedure call was still running but did not stream progress. | Use a separate query/worksheet to watch `TASK_HISTORY` or run a status script like `scripts/check_backfill.py`. |
| `python -c "complex code"` failed with quoting errors | The shell mangled embedded quotes / asterisks / semicolons. | Put the code in a `.py` script and run that instead of a one-liner. |
| Command output repeated the command line before the result | This tool echoes the command; it is not an error. | Wait for the final exit code and output block. |

### 11.2 Use separate terminal windows/tabs

Open at least three views so you can see state without re-running commands:

1. **Git status window**
   ```powershell
   git status --short
   git log --oneline -5
   git diff --stat
   ```
2. **Validation window**
   ```powershell
   pytest pipeline/tests -q
   ruff check pipeline ui scripts
   python scripts/check_backfill.py
   python scripts/check_task_history.py
   ```
3. **Deploy / live checks window**
   ```powershell
   python pipeline/deploy/deploy.py --client eastofengland --task-off
   python scripts/validate_merge_snowflake.py
   ```

Keep these open and re-run the relevant one after each action. This prevents the "what is it doing now?" problem.

### 11.3 Safe command patterns

**Bad (easy to hang or mis-quote):**

```powershell
git add file1 file2; git commit -m "long message"; git push origin branch
python -c "import sys; ... cur.execute(\"SELECT COUNT(*) FROM ...\")"
```

**Good:**

```powershell
git add file1 file2
git commit -m 'short clear message'
git push origin branch
```

```powershell
python scripts/my_query.py
```

### 11.4 If a command seems stuck

1. **Do not cancel immediately.** Check whether it is still producing output or just slow (Snowflake queries can take minutes).
2. **Open another terminal** and run a status command to confirm progress.
3. **If it is waiting for input** (e.g., Git credentials), cancel it (`Ctrl+C`), fix the underlying issue (cache credentials, fix quotes), then retry.
4. **If it is a long Snowflake job**, let it finish; use `TASK_HISTORY` or a status script to watch it.

### 11.5 Time/cost traps to avoid

- **Repeated full backfills:** each redeploy + backfill can take an hour and rack up warehouse credits. Avoid by validating schema and deploy scripts before the first deploy.
- **Rerunning long pytest suites unnecessarily:** run only the affected tests first (`pytest path/to/test.py`), then the full suite once.
- **Interactive git prompts inside non-interactive tools:** if a tool runs git for you, make sure credentials are cached and messages are quoted correctly.
- **One-liner Python with complex SQL:** always prefer a script file; it is easier to read, rerun, and debug.

## 12. What made the 2026-07-30 merge expensive

- The integration branch was created after a large amount of drift had already accumulated.
- Conflicts spanned pipeline core, UI, deploy scripts, tests, workflows, and docs.
- A stale Snowflake zip caused daily runs to fail for a week; fixing it required redeploy + 8-day backfill.
- Validation and documentation were done inline with the merge, which is necessary but time-consuming.

**Next time:** smaller merges, pre-merge `merge-tree`, deploy dry-run before committing, and a stricter "no merge until tests + lint + dry-run are green" rule.
