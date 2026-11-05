# Cluster Dashboard — weekly refresh (PM guide)

What this is: the dashboard is a **static page updated weekly** from a pull of
the last 7 days across the **14 pilot stores**. Each week the data produces
*candidate trends* — you decide which ones go in. Once you've picked, a PR is
opened to update the page; merging it publishes the refresh.

## Your weekly loop

1. Ask the agent (Devin/Claude) in this codebase:

   > **"Refresh the cluster dashboard."**

   It runs three read-only Snowflake pulls and regenerates the store table and
   open-action lists automatically.

2. It shows you a **candidate table** like:

   | # | Candidate | Stores | Signal | ~£ at stake |
   |---|---|---|---|---|
   | 1 | Soft Drinks | 13 | drops + slot alerts | £33k |
   | 2 | Cigarettes | 9 | drops + slots | £18k |
   | 3 | Coffee (upstream) | 9 | inventory=0 gap 15pp | — |

   plus a previous-week comparison (persistent / new / resolved).

3. **You pick.** Just reply, e.g. *"keep 1, 2 and 5"*. Your picks are recorded
   in the candidates JSON (`keep: true`) — that file is the review record for
   the week.

4. Say **"open the PR"** — the agent builds the kept trends into tiles, runs
   the checks, and opens a pull request on `store-insight-ui`. Review the PR
   (or have someone review it), merge, done — that's the weekly update shipped.

## How to judge candidates

- **Stores affected** — a trend spanning most of the 14 stores is usually a
  shared cause (worth a tile); 1–2 stores is often noise.
- **Persistent vs new** — flagged two weeks running = the real problem list;
  new this week = worth watching.
- **£ at stake** — pipeline estimated lost sales; rank by it when in doubt.
- **Three groups**: (1) causes stores *told us* in action notes, (2) sections
  with availability drops/replenishment gaps, (3) loss where inventory was
  zero — nothing in the store to sell, i.e. not the store's fault.

## What you never need to do

- Touch Snowflake — pulls are read-only and scripted; nothing is written back.
- Edit code — the agent + `regen_cluster_fixtures.py` handle everything.
- Git mechanics — branch, commit, PR are all done for you. You just say "open
  the PR" and review what comes out.

## If the pull fails

Snowflake auth uses browser SSO — a browser window may open; sign in and the
pull continues. If credentials are missing entirely, the pull can't run — flag
it, don't work around it.
