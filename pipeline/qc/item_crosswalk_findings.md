# WMD ↔ OSA Item Crosswalk — Accepted Approach

**Source:** `pipeline/qc/item_crosswalk_qc.ipynb` (read-only profiling against Snowflake, `eastofengland` client)
**Goal:** Find a reliable way to join WMD waste/markdown-sales facts to OSA/LSM availability data at item level.

## Accepted crosswalk: direct via `WMD_ITEM_HIERARCHY.HIERARCHY_LEVEL_1_ID`

Chain — skips `ANALYSIS.FINAL.ITEM` entirely:

```
LSM_ITEM_HIERARCHY.ITEM_ID  ==  WMD_ITEM_HIERARCHY.HIERARCHY_LEVEL_1_ID
WMD_ITEM_HIERARCHY.EAN/ITEM_ID  ==  WMD_WASTAGE/WMD_SALES fact tables
```

**Findings:**
- `LSM_ITEM_HIERARCHY.ITEM_ID` matches `WMD_ITEM_HIERARCHY.HIERARCHY_LEVEL_1_ID` for **93.8%** of WMD hierarchy values (129,147 / 137,625). `MASTER_ITEM_ID` gives an identical result.
- **End-to-end coverage: 88.5% of waste rows (78.6% of quantity)** and **89.2% of markdown-sales rows** resolve to an LSM item through this chain.
- **Confirmed fan-out**: `WMD_ITEM_HIERARCHY` has 156,952 rows (each with a unique `ITEM_ID`) but only 137,625 distinct `HIERARCHY_LEVEL_1_ID` values. So **one `HIERARCHY_LEVEL_1_ID` maps to several WMD `ITEM_ID` rows** — worst case, 78 WMD items sharing one `HIERARCHY_LEVEL_1_ID`.
  - The fan-out direction is favourable: it's on the WMD (fact) side, not the OSA/availability side. As long as WMD facts are `SUM`'d / aggregated per `HIERARCHY_LEVEL_1_ID` **before** joining to `LSM_ITEM_HIERARCHY.ITEM_ID`, there's no risk of duplicating OSA rows.
  - A distribution query (how many `HIERARCHY_LEVEL_1_ID` values map to 1, 2, 3... WMD items) has been added to the notebook but not yet run — worth doing before rollout to size the aggregation risk precisely.

**Verdict: this is the crosswalk to use**, provided WMD facts are pre-aggregated by `HIERARCHY_LEVEL_1_ID`.

---

## Side note — existing code smell

`pipeline/adapters/eastofengland/wmd_hierarchy.sql` currently aliases `HIERARCHY_LEVEL_1_ID` as `OSA_ITEM_CODE` under the assumption it's a division-level grouping key (per `pipeline/contracts/wmd_join_check_report.md`). These findings suggest it actually behaves much more like an item-level code (93.8% match rate against `LSM_ITEM_HIERARCHY.ITEM_ID`, ~5x fact coverage) — just with a confirmed one-to-many fan-out on the WMD side that the existing alias doesn't account for. Worth revisiting that adapter once the aggregation step is implemented.

---

## Recommended next step

Implement the join as:

```sql
WITH wmd_agg AS (
    SELECT
        HIERARCHY_LEVEL_1_ID,
        SUM(waste_quantity) AS waste_quantity,  -- or relevant measure
        ...
    FROM WMD_WASTAGE w
    JOIN ANALYSIS.FINAL.WMD_ITEM_HIERARCHY wh ON w.EAN = wh.EAN
    GROUP BY HIERARCHY_LEVEL_1_ID
)
SELECT ...
FROM wmd_agg
JOIN ANALYSIS.FINAL.LSM_ITEM_HIERARCHY lsm
  ON wmd_agg.HIERARCHY_LEVEL_1_ID = lsm.ITEM_ID
```

Full step-by-step evidence is in `pipeline/qc/item_crosswalk_qc.ipynb` (Section 10).
