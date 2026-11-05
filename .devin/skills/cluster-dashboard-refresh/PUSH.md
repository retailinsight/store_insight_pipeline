# Open the weekly refresh PR — agent instructions

**Paste this block to the agent once the PM has chosen which candidates to
keep and said to open the PR.**

---

You are opening a PR on `store-insight-ui` with this week's Cluster Dashboard
refresh — fixture updates only (static page, no API/Snowflake writes).

## Preconditions — check before doing anything

1. The newest `scripts/out/cluster_trend_candidates_*.json` exists and the
   PM's picks are marked (`keep: true` on approved candidates only). If not,
   STOP — do not PR unreviewed data.
2. The pulls for this week ran (metrics + trends + notes JSONs in
   `scripts/out/` all dated this week, matching windows).

## Before the PR

- Regenerate: `python regen_cluster_fixtures.py` in `store_insight_pipeline/scripts/`.
- Build the kept candidates into tiles/panels per
  `.devin/skills/cluster-dashboard-refresh/SKILL.md` step 4 — every number in
  tile copy must trace to the pull JSONs.
- Update `dataPulledAt` in `clusterFixture.ts`.
- Verify: `npx tsc --noEmit`, `npm test` (UI suite), and `node --check` the
  extracted `<script>` if the standalone HTML was regenerated. All heatmap
  rows = 7 cells; every store's `open` count == its action-item count.
- **Secrets scan** before staging: `git diff` for `eyJ`, `PRIVATE KEY`,
  credentials — fixtures contain data only, never connection details.

## The PR

- Branch: `feat/cluster-dashboard-YYYY-MM-DD` (window end date).
- Commit only the fixture/component changes — `src/data/cluster*.ts`,
  `clusterFixture.ts`, `clusterStoreFixture.ts`, `clusterOpenActionsFixture.ts`,
  any component edits. Do NOT commit `scripts/out/*.json` (raw pull data stays
  local — it may contain store-specific detail not needed in the repo).
- Title: `Cluster Dashboard — week ending <date>: <kept trends>`

```markdown
## Summary
- Weekly refresh: last 7 days ending <date>, 14 pilot stores
- Kept trends: <list, e.g. Soft Drinks (13 stores), Cigarettes (9), Coffee upstream gap (9)>
- Rejected: <candidates not kept, one line>
- Store table + open actions regenerated from <metrics json filename>

## Evidence
Candidates JSON: scripts/out/cluster_trend_candidates_<ts>.json (local, not committed)
Reviewed by: <who picked>

## Test plan
- [ ] tsc clean, UI tests pass
- [ ] /cluster-preview: tiles render, panels open, counts consistent
- [ ] No credentials or raw pull JSON in the diff
```

- Open with `gh pr create`. **Do not merge** — the PM reviews the PR itself.
- Report the PR URL and a one-line summary of what changed.

## Hard rules

- Fixture data only — never commit candidates JSONs, credentials, or `.env`.
- No pushing to `master` directly; PR only.
- If verification fails, fix or report — never force the PR through red checks.

---
