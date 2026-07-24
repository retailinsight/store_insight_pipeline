---
description: Turn a grilled conversation (or a described problem) into a destination PRD — a markdown file that captures the shared design concept
---

Write a Product Requirements Document that captures everything decided so far. The PRD is the **destination document** — it describes where we are going, not how we will get there.

## Inputs

- The current chat history, especially any preceding `/grill-me` session.
- If no grilling happened yet, **first ask the user for a long, detailed description of the problem**, then run a short grilling pass (one question at a time, with recommendations) to fill obvious gaps. **Explore the codebase before asking anything the repo can answer.**

## Output

Write a single file: `prds/<feature-slug>/PRD.md`

`<feature-slug>` is lowercase kebab-case, ≤ 40 chars, derived from the feature name. Create the directory if it does not exist. If a PRD already exists at that path, ask before overwriting.

## Required sections (in this order)

```markdown
# <Feature Name>

## Problem
One or two paragraphs. Who is affected, what is currently broken or missing, why it matters.

## Solution
One or two paragraphs. The approach at a high level — not implementation detail.

## User stories
Numbered list. Format: "As a <role>, I can <action> so that <outcome>."
Cover the happy path and the important edge paths.

## Module map
Bulleted list of modules to be created or modified, with one line each on what changes.
Group by: new modules, modified modules, deleted modules.
This is the bridge from PRD to code — it forces us to keep the codebase shape in mind.

## Implementation decisions
Bulleted list of non-obvious decisions made during grilling. Include the decision and the rationale.
Examples: idempotency strategy, retroactivity / backfill behavior, default thresholds, failure-mode handling, observability hooks.

## Testing decisions
Bulleted list. What gets unit-tested, what gets integration-tested, what gets manual-QA'd, where the test boundary sits.

## Out of scope
Bulleted list of things a reasonable reader might assume are included but are NOT.
This section is as important as the user stories — it is the negative space that defines done.
```

## Rules

- **Do not read the file back to the user after writing it.** The user will not review it line-by-line; alignment was reached during grilling. You are summarizing, not negotiating.
- **Propose the module map before writing the file.** Show the user the list of modules you intend to create/modify and wait for a yes/no/edit. This is the one part of the PRD where their eyeballs matter most — it is where the PRD touches code.
- **Prefer deep modules over shallow ones** (Ousterhout): a few modules with rich behavior behind small interfaces, not many tiny files. Reflect this in the module map.
- **No implementation steps, no phases, no task breakdown.** That is `/prd-to-issues`' job. The PRD describes the destination, not the journey.
