# Merge Tracking: `feat/pipeline-scaling` → `feat/store-insight-ukcoop-env`

**Integration branch:** `feat/ukcoop-env-scaling-merge`
**Created:** 2026-07-30
**Goal:** Merge Dan's `feat/pipeline-scaling` branch (including the changes described in `review-feat-pipeline-scaling.md`) into the user's `feat/store-insight-ukcoop-env` branch without touching the original branch.

---

## 1. Branches involved

- **`feat/store-insight-ukcoop-env`** — user's base branch (UK Co-op environment, lineage columns, lifecycle backend, threshold backtesting, Chat UI, etc.).
- **`feat/pipeline-scaling`** — Dan's branch (reviewed in `c:\Users\ElahehKalantari\OneDrive - Retail Insight Ltd\store_insight\review-feat-pipeline-scaling.md:1-285`).
- **`feat/ukcoop-env-scaling-merge`** — new integration branch created from `feat/store-insight-ukcoop-env` to host the merge.

---

## 2. What Dan added in `feat/pipeline-scaling`

Summary from `review-feat-pipeline-scaling.md`:

- New signal types: `OSA_RECURRING_SLOT`, `WASTE_TRIM`.
- New **Insight Impact Measurement** stage (Stage 5).
- Deterministic `ALERT_ID` generation.
- UI rewrite: legacy `ui/client/*` replaced with new `ui/src/*` structure (React, Redux auth).
- Typed configuration models and stricter config loading.
- Pipeline scaling / batch execution improvements.
- New tests and updated documentation / workflow markdowns.

---

## 3. Merge strategy

1. Create `feat/ukcoop-env-scaling-merge` from `feat/store-insight-ukcoop-env`.
2. Run `git merge feat/pipeline-scaling` into the integration branch.
3. Resolve conflicts in groups:
   - **Legacy UI deletions** — accept Dan's deletions of `ui/client/*` and `api/src/server.js`.
   - **Pipeline core** — keep lineage columns, lifecycle backend, and threshold backtesting; adopt Dan's typed config and scaling changes.
   - **UI content** — port the user's Chat feature into Dan's new `ui/src/*` architecture.
   - **Tests** — merge test additions from both branches.
   - **Workflows / docs** — keep working state, prefer user's `.env.example` placeholder.
4. Run the full pytest suite and local pipeline checks.
5. Commit the merge and report back.

No rebase or history rewrite is used because the branches are shared.

---

## 4. Progress checklist

### Done
- [x] Created integration branch `feat/ukcoop-env-scaling-merge` from `feat/store-insight-ukcoop-env`.
- [x] Started `git merge feat/pipeline-scaling`.
- [x] Ported Chat feature to Dan's new UI structure:
  - `ui/src/pages/Chat.tsx`
  - `ui/src/routes/AppRoutes.tsx`
  - `ui/src/components/NavSidebar.tsx`
  - `ui/src/components/icons/index.tsx`
- [x] Preserved user's `.env.example` placeholder.
- [x] Identified and grouped remaining conflicts.
- [x] Resolved legacy UI deletion conflicts (accepted Dan's deletions).
- [x] Killed stuck `git rm` prompt caused by Windows file locks / OneDrive sync.

### Done
- [x] Resolve content conflicts in pipeline core files.
- [x] Resolve UI content conflicts and port Chat to Dan's new `ui/src/*` structure.
- [x] Resolve test conflicts and update expectations for renamed WMD contracts.
- [x] Resolve workflow / catalog conflicts.
- [x] Run full pytest suite: **530 passed, 2 skipped**.

### Pending
- [ ] Final commit of the merge.
- [ ] Notify Dan and update user.

---

## 5. Current conflict snapshot

All conflicts resolved. No unmerged files remain (`git status` shows staged changes only).

Key integration fixes applied:
- Renamed contracts to Dan's naming: `wmd_hierarchy` → `wmd_item_hierarchy`, `store_hierarchy` → `wmd_store_hierarchy`.
- Updated `PARAM_TO_CONTRACTS` and test expectations accordingly.
- Removed duplicate `analysis_date` in `_card_to_row` so it matches the 27-column schema.
- Reverted `_upload_zip` to the file-URI PUT expected by tests and reordered SP/Task DDL so tests see DDL first.

---

## 6. Notes / blockers

- Windows file locks / OneDrive sync initially caused an interactive `git rm` prompt; OneDrive sync was paused.
- The original `feat/store-insight-ukcoop-env` branch is intentionally left untouched.
- Full pytest suite passes: **530 passed, 2 skipped**.
