# PR #108 — 'Cost if Not Actioned' wording examples

Real DEV card data (`STORE_INSIGHT_DEV`, latest run per type) passed through the PR #108 narrative code.
Shows: what the card says today, what it will say after this PR, and the fallback text used when no valid cost figure exists.

| Card type | Store | Today (current DEV text) | After PR #108 | When cost is zero / missing |
|---|---|---|---|---|
| `BINNED_WASTE` | 213 | Estimated waste cost: £1510 projected over 4 weeks<br>Based on the last 7 days of waste data. Actual costs may vary. | Estimated waste cost: £1510 projected over 4 weeks<br>Based on the last 7 days of waste data. Actual costs may vary. | If this continues, binned waste will keep accumulating. |
| `COMPLIANCE` | 205 | £224.81 per week if not fixed. | If this continues, there is a risk that the store could lose £899.24 in lost sales in the next 4 weeks. | Alerts closed without investigation risk leaving real availability issues unresolved. |
| `MARKDOWN_OVERRIDE` | 224 | Items overridden at a higher price are at increased risk of reaching end-of-life unsold, driving unnecessary waste. | If this continues, the store could lose approximately £2,045.16 in the next 4 weeks through unnecessary overrides. | Items overridden at a higher price are at increased risk of reaching end-of-life unsold, driving unnecessary waste. |
| `MARKDOWN_SKU` | 409 | An item requiring markdown every week represents a recurring ordering cost and waste risk. If quantities are not adjusted, this pattern is likely to continue. | An item requiring markdown every week represents a recurring ordering cost and waste risk. If quantities are not adjusted, this pattern is likely to continue. | An item requiring markdown every week represents a recurring ordering cost and waste risk. If quantities are not adjusted, this pattern is likely to continue. |
| `OSA_BIG_DROP` | 214 | If Tuesday's rate of loss continued, store-controlled lost sales could cost approximately £577.08 over the next 4 weeks. | If Tuesday's rate continued, the store could lose approximately £577.08 in sales over the next 4 weeks. | If Tuesday's rate continued, the store would keep losing sales. |
| `OSA_RECURRING_SLOT` | 210 | If these lines keep running short in this slot, the store could lose approximately £69.52 over the next 4 weeks. | If these lines keep running short in this slot, the store could lose approximately £69.52 over the next 4 weeks. | If these lines keep running short in this slot, the store will continue to lose sales. |
| `OSA_STORE_ACTIONABLE` | 204 | If this continues at the same rate, store-controlled lost sales could cost approximately £1,226.60 over the next 4 weeks. | If this continues, the store could lose approximately £1,226.60 in lost sales in the next 4 weeks. | If this continues, the store risks further lost sales over the coming weeks. |
| `PROMPTED_MARKDOWN_COMPLIANCE` | 204 | £0.00 per week if not fixed. | If compliance continues to fall, straight-to-bin waste is likely to increase. | If compliance continues to fall, straight-to-bin waste is likely to increase. |

## Key changes

- `PROMPTED_MARKDOWN_COMPLIANCE` currently displays **`£0.00 per week if not fixed`** — the PR replaces this with a qualitative risk sentence.
- All other types now project costs over **4 weeks** with consistent "the store could lose approximately £X" wording.
- `OSA_BIG_DROP` keeps its explicit basis ("If Tuesday's rate continued...") as requested in review.
- No card can render £0.00 — every cost-emitting generator falls back to a qualitative sentence via `_cost_or_fallback`.

## Still open in review

- The same £ figure still leaks into the card `explanation` on `MARKDOWN_COMPLIANCE` / `PROMPTED_MARKDOWN_COMPLIANCE` (Bryan asked to patch).
- Rebase onto current `main` (`bc7faf5`) and re-run CI.