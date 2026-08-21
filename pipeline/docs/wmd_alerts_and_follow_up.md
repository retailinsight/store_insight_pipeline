# WMD Alerts and Follow-up Work

## Purpose

The WMD alert suite identifies markdown, waste, and sell-through issues from the WMD operational data. It complements OSA alerts by identifying products that are being marked down, wasted, or cleared unusually often.

## Alert Types

| Alert type | Question answered | Primary sources |
|---|---|---|
| `MARKDOWN_OVERRIDE` | Are stores overriding markdown decisions more often than the chain or than last week? | WMD markdown log |
| `MARKDOWN_SELLTHROUGH` | Are markdown items selling through less effectively than the chain or than last week? | WMD markdown sales and markdown log |
| `MARKDOWN_SKU` | Is a specific product repeatedly requested for markdown or receiving excessive overrides? | WMD markdown log and WMD item hierarchy |
| `WASTE` | Is a store wasting more markdown-handled stock than the chain or than last week? | WMD wastage, markdown log, and WMD item hierarchy |
| `WASTE_TRIM` | Is an OSA product selling a high proportion of units at markdown? | WMD markdown sales, WMD item hierarchy, OSA sales, and LSM item hierarchy |

## WASTE_TRIM

`WASTE_TRIM` is a product-level alert. It flags a store-product when the markdown-sales ratio is above the configured threshold and markdown unit volume meets the configured minimum.

```
markdown ratio = markdown units / (markdown units + OSA actual-sales units)
```

The OSA actual-sales measure excludes markdown sales, so markdown units must be added to form the complete sales denominator.

### Item Crosswalk

WMD and OSA do not share the same child item identifier. The crosswalk is:

```
WMD_SALES.ITEM_ID
  -> WMD_ITEM_HIERARCHY.ITEM_ID
  -> WMD_ITEM_HIERARCHY.HIERARCHY_LEVEL_1_ID
  -> LSM_ITEM_HIERARCHY.ITEM_ID / MASTER_ITEM_ID
  -> OSA.ITEM_CODE
```

`HIERARCHY_LEVEL_1_ID` is exposed in `WMD_HIERARCHY_V1` as `OSA_ITEM_CODE`.

Several WMD child products can map to one OSA parent product. Markdown units and markdown value are therefore aggregated to `OSA_ITEM_CODE` before they are combined with OSA actual sales. This prevents assigning the same OSA sales denominator independently to each child WMD item.

### Example

For store `292`, WMD item `4238` (`CP BANANAS`) maps to OSA item `747517` (`CP FAIRTRADE BANANAS`). For 2026-03-14 to 2026-03-20:

- Markdown units: `1,733`
- OSA actual-sales units: `3,083`
- Total units: `4,816`
- Markdown ratio: `35.98%`

This does not pass the default `WASTE_TRIM` threshold of more than `40%`.

## Deployment

The WMD hierarchy adapter must be deployed after changes:

```text
pipeline/adapters/eastofengland/wmd_hierarchy.sql
```

The end-to-end QC notebook redeploys this view before it loads WMD data. Production deployment should use the normal adapter deployment process before the next batch run.

## Downstream Follow-up Work

### Before enabling or relying on the alert

- Confirm `WMD_HIERARCHY_V1` includes `OSA_ITEM_CODE` in the production environment.
- Run the QC pipeline for a representative set of stores and compare alert counts with the previous run.
- Check examples where WMD child items share an OSA parent to confirm markdown units are intentionally aggregated.
- Confirm the product and department shown on alerts come from the OSA parent item.

### Data-quality monitoring

- Monitor the weekly share of markdown store-items that map through `OSA_ITEM_CODE` to OSA sales.
- Alert on a material drop from the validated 84.66% usable crosswalk rate for the week ending 2026-03-20.
- Report WMD items with no `HIERARCHY_LEVEL_1_ID` and mapped OSA parents with no OSA sales during the alert week.
- Review source hierarchy refreshes for changes to the WMD child-to-OSA-parent mapping.

### Alert-product follow-up

- Confirm the `WASTE_TRIM` threshold and minimum markdown-unit threshold with commercial stakeholders after the first production run.
- Review whether the `markdown_value` cost proxy should be supplemented with margin or full-price sales opportunity when a reliable source becomes available.
- Add automated detector tests using a fixture where multiple WMD child items map to one OSA parent.
- Add a QC output showing WMD child IDs, their shared OSA parent, markdown units, actual-sales units, and the final ratio for every `WASTE_TRIM` alert.
- Add crosswalk coverage and unmapped-item counts to operational monitoring.
