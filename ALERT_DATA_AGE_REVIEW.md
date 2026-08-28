# Alert timing review — how old is the data behind each action?

**Date:** 2026-08-24 (updated **2026-08-28** — see the box below). **For:** Dave and Dan's action-by-action review this week.
**Written by:** Elaheh.

> **28 Aug update — the “one batch, all D-1” premise no longer holds.** The 11:30
> source checks on 27 and 28 Aug show each feed has its own natural lag:
> `osa`/`markdown_log` land at **X+1**, but `feedback`, `markdown_sales` and
> `wastage` are only reliably complete at **X+3** (feedback's X+2 day was ~72%
> filled on 28 Aug; markdown_sales/wastage were X+3 on 27 Aug, X+2 on 28 Aug).
> What changes for this review:
>
> - **Worst case data age is X+3, not X+2** — for FEEDBACK-driven actions
>   (COMPLIANCE) and the markdown_sales/wastage inputs to the three ratio checks.
> - **Moving the run to ~09:15 no longer gives D-1 for every feed** — only for
>   osa/markdown_log. The three lagging feeds stay 2–3 days behind regardless
>   of run time, so the mismatch risk in WASTE / WASTE_TRIM /
>   MARKDOWN_SELLTHROUGH is structural, not a run-time problem. The real fix
>   for those is aligning detector windows to the min(max-date) across a
>   check's feeds.
> - The 11:30 source check now expects each feed's own lag
>   (`fix/source-check-per-source-lag`), so `DATA_QUALITY_LOG` only flags
>   genuine shortfalls.
>
> The per-action table below still describes which feeds each action uses; read
> its “Window” ages against the per-feed lags above rather than a single D-2/D-1.

## Read this first

All five source feeds land in Snowflake in one batch between **08:30 and
08:40 UK** each day (checked with time travel over the last four days). Each
load brings data up to **yesterday** (D-1).

So the run time sets the data age for every action:

- **Run at 06:00 (today):** the newest data is from **two days ago** (D-2).
- **Run at ~09:15 (proposed):** the newest data is from **yesterday** (D-1).

Dan's view: day-old data is fine because we mostly look for week-on-week
drops. Dave asked to sense-check that per action. The table below gives the
facts for each one. The right-hand column is my read; the call is Dave's.

## The five feeds

| Feed | What it holds |
|---|---|
| OSA | Daily availability: sales and lost sales per store-item |
| WASTAGE | Daily waste quantities per store-item |
| MARKDOWN_SALES | Daily sales of marked-down lines (WMD) per store-item |
| MARKDOWN_LOG | Each markdown request and whether staff overrode it |
| FEEDBACK | How stores worked their alerts (LSM alert feedback) |

## Per action

"Window" is the date range the check reads. All windows end at the newest
data the run can see — D-2 today, D-1 at 09:15.

| Action (alert type) | Checks | Feeds used | Window | Does a day's lag matter? |
|---|---|---|---|---|
| OSA | WOW, VS_CHAIN | OSA only | This week vs last week (WOW); this week vs chain (VS_CHAIN) | **Low risk.** One feed, so no mismatch. Week-on-week and vs-chain compare like with like; a day's lag shifts both sides the same way. |
| OSA (repeat) | REPEAT | OSA only | Rolling 10 weeks | **Low risk.** Ten-week pattern; one day makes no real odds. |
| OSA_RECURRING_SLOT | recurring slot | OSA only | Rolling 10 weeks | **Low risk.** Same as above. |
| WASTE | WOW, VS_CHAIN | WASTAGE + MARKDOWN_LOG | This week vs last week; this week vs chain | **Watch.** Two feeds in one ratio (waste ÷ markdowns). Fine while both feeds land in the same batch — but if one ever backfills later than the other, the ratio skews. The 05:30 check would show this. |
| WASTE_TRIM | trim ratio | MARKDOWN_SALES + OSA | This week | **Watch — this is the one that swung.** Ratio of WMD sales to (WMD + OSA sales). When the two feeds held different day counts at 06:00, alerts went from ~40 to ~750 a day. Same-batch arrival plus a later run removes the skew; the cap (live from 25 Aug) limits the blast either way. |
| MARKDOWN_SKU | REPEAT_REQUEST, EXCESSIVE_OVERRIDE | MARKDOWN_LOG only | Rolling 4 weeks | **Low risk.** One feed, multi-week pattern. (REPEAT_REQUEST fell to zero in the incident because the feed was 4 days stale, not 1 — a day's lag is fine.) |
| MARKDOWN_OVERRIDE | WOW, VS_CHAIN | MARKDOWN_LOG only | This week vs last week; this week vs chain | **Low risk.** One feed, like-for-like compare. |
| MARKDOWN_SELLTHROUGH | WOW, VS_CHAIN | MARKDOWN_LOG + MARKDOWN_SALES + WASTAGE | This week vs last week; this week vs chain | **Watch.** Three feeds in one proxy (sales after markdown ÷ sales + waste). Same story as WASTE: safe while all three land together, skewed if they ever split. |
| COMPLIANCE | TICK_AND_FLICK | FEEDBACK only | This week vs last week, vs chain | **Low risk for the maths** — one feed, like-for-like. **But note:** this action is about how stores work alerts, so the freshest view helps coaching conversations. D-1 at 09:15 is still a day fresher than what stores get today. |

## What this says overall

- **No action needs same-day data.** Every check is a weekly compare or a
  multi-week pattern. Dan's w-on-w reasoning holds for all nine.
- **The risky ones are the three multi-feed ratios** (WASTE, WASTE_TRIM,
  MARKDOWN_SELLTHROUGH). Their danger is not data age — it is feeds holding
  *different* ages. Running after the 08:40 load (e.g. 09:15) means every
  feed holds the same max date, which removes the mismatch by design.
- **Staying at 06:00 keeps the mismatch risk** whenever backfills split
  (as they did 19–22 Aug), and always costs one extra day of staleness.
- The 05:30 source check logs each feed's lag daily, so if the 08:30–08:40
  pattern ever moves we will see it in `DATA_QUALITY_LOG`.

**My read:** move the run to ~09:15. Stores get alerts ~3 hours later, but
every action gets fresher data and the three ratio checks get matched feeds.
Dave decides whether the 3-hour delay hurts store routines.
