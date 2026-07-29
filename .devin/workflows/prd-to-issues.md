---
description: Break a PRD into independently-grabbable GitHub issues using vertical slices (tracer bullets), with explicit blocking relationships
---

Take a PRD and produce a **kanban board** of GitHub issues: small, independently-grabbable units of work with explicit blocking relationships. Optimize for **vertical slices**, not horizontal layer-by-layer phases.

## Prerequisites

- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated (`gh auth status`). If missing or unauthenticated, stop and tell the user to install/`gh auth login` before continuing.
- The repo's GitHub remote must be reachable — confirm with `git remote get-url origin`. Derive `<owner>/<repo>` from it (currently `dantretailinsight/store_insight`) for use with `gh issue create --repo <owner>/<repo>` if `gh` isn't already scoped to this repo by cwd.

## Inputs

- A path to an existing PRD, e.g. `prds/<feature-slug>/PRD.md`. If none was given, list available PRDs and ask.
- The current codebase. **Re-explore before drafting** — the codebase shape determines what a good slice looks like.

## Output

One GitHub issue per slice, created via `gh issue create`. Publish in dependency order (blockers first) so real issue numbers can be referenced in later issues' "Blocked by" section — GitHub has no native blocking field, so this is expressed in the issue body.

```
gh issue create \
  --title "<NN> — <Issue Title>" \
  --body "<rendered template>" \
  --label "<type label, e.g. afk or human-in-the-loop>"
```

Capture the returned issue URL/number after each create so it can be referenced by later slices.

## Issue body template

```markdown
**Type:** AFK | human-in-the-loop
**Blocked by:** <none> | #<issue-number> (link), or slice title if not yet published
**Blocks:** <none> | #<issue-number> (link), or slice title if not yet published

## Goal
One sentence: what observable change does this issue produce?

## Vertical slice
Bulleted list of the layers touched (data model, service, API, UI, etc.) and the minimal change in each. The end of this issue should produce something a human can see or run end-to-end.

## Acceptance
Bulleted checklist of conditions that must be true when this issue is done.
Include: tests pass, types pass, the slice is visible/usable by a human.

## Notes
Any non-obvious context, references to existing modules, or links to PRD sections.
```

## Rules

- **Vertical slices, not horizontal phases.** A good first slice touches schema + service + a minimal piece of UI/output, so feedback is available immediately. A bad first slice is "all the database changes" or "all the new services with no integration."
- **Independently grabbable.** Each issue should be doable by a single agent in one session, given only the issue body, the PRD, and the codebase. If an issue requires three other issues to be merged first, split or sequence it.
- **Explicit blocking, not implicit phases.** Express order as a DAG via `Blocked by:` / `Blocks:`. Multiple unblocked issues at the same level can be parallelized.
- **Tag every issue.** `AFK` = an agent can complete it without human input (clear acceptance, deterministic feedback loops). `human-in-the-loop` = needs taste, design choices, or external info. Apply as a `gh issue create --label` where a matching label exists in the repo (`gh label list`); otherwise note the type in the body only and don't invent new labels without asking.
- **Propose the slice list first.** Before creating any issues, show the user the proposed issues (titles + types + blocking relationships) and wait for confirmation. Watch for slices that are too horizontal — push back on yourself if the first slice does not produce something visible.
- **Keep a final QA / polish issue.** Last issue, blocked by everything, type `human-in-the-loop`, for end-to-end QA and follow-up tickets.
- **Publish in dependency order.** Create blockers before the issues they block, so `Blocked by:`/`Blocks:` can reference real `#<number>` links instead of placeholder slice titles.
- **Do not read the issue bodies back to the user.** Confirm the slice list, create the issues via `gh issue create`, report the resulting issue URLs, stop.
