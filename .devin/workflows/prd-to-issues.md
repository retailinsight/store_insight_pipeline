---
description: Break a PRD into independently-grabbable issue files using vertical slices (tracer bullets), with explicit blocking relationships
---

Take a PRD and produce a **canban board** of issue files: small, independently-grabbable units of work with explicit blocking relationships. Optimize for **vertical slices**, not horizontal layer-by-layer phases.

## Inputs

- A path to an existing PRD, e.g. `prds/<feature-slug>/PRD.md`. If none was given, list available PRDs and ask.
- The current codebase. **Re-explore before drafting** — the codebase shape determines what a good slice looks like.

## Output

One markdown file per issue, written to the same directory as the PRD:

```
prds/<feature-slug>/
├── PRD.md
├── 01-<slug>.md
├── 02-<slug>.md
└── ...
```

## Issue file template

```markdown
# <NN> — <Issue Title>

**Type:** AFK | human-in-the-loop
**Blocked by:** <none> | 01, 03
**Blocks:** <none> | 04

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
- **Tag every issue.** `AFK` = an agent can complete it without human input (clear acceptance, deterministic feedback loops). `human-in-the-loop` = needs taste, design choices, or external info.
- **Propose the slice list first.** Before writing any files, show the user the proposed issues (titles + types + blocking relationships) and wait for confirmation. Watch for slices that are too horizontal — push back on yourself if the first slice does not produce something visible.
- **Keep a final QA / polish issue.** Last issue, blocked by everything, type `human-in-the-loop`, for end-to-end QA and follow-up tickets.
- **Do not read the issue files back to the user.** Confirm the slice list, write the files, report the paths, stop.
