---
description: Implement an AFK issue using TDD (red-green-refactor), run feedback loops (tests + types), and commit
---

Implement a single AFK issue from the canban board using Test-Driven Development and commit when the acceptance criteria are met.

## Inputs

- A path to an issue file, e.g. `prds/<feature-slug>/01-<slug>.md`. If none given, list available issues and ask.
- The current codebase. Read the PRD in the same directory to understand context.

## Steps

1. **Read the issue and PRD.** Load the issue file and the `PRD.md` in the same directory. Understand the goal, vertical slice, and acceptance criteria.

2. **Explore the codebase.** Before writing any code, explore the target area using `code_search`, `grep_search`, and `read_file`. Understand the existing patterns and conventions. Do not make assumptions.

3. **TDD cycle — red → green → refactor.**

   - **Red:** Write a failing test (or add to an existing test file) that exercises the new behavior. Run the test to confirm it fails.
   - **Green:** Write the minimal code to make the test pass. Do not skip the red step.
   - **Refactor:** Clean up the implementation if needed, keeping the test green.

   Repeat this cycle until all acceptance criteria from the issue are met.

4. **Run feedback loops.** Before declaring done:

   - Run `pytest` on the full test suite. All tests must pass.
   - Run `ruff check .`. No errors.
   - If the issue mentions types or mypy, run that too.

5. **Propose a commit message.** Show the user a Conventional Commits-style message (`feat:`, `fix:`, `refactor:`, etc.) with a subject line ≤ 72 chars, imperative mood, no trailing period. Wait for confirmation or an edit.

6. **Commit.** Stage all changes and commit with the confirmed message. Do not push yet — the user may want to review before pushing.

7. **Report the outcome.** Tell the user what files were changed, what tests now pass, and the commit SHA.

## Rules

- **One issue per chat.** This workflow is designed for a single issue. Do not try to chain multiple issues in one session.
- **Respect the issue's vertical slice.** Do not implement beyond what the issue describes. If the issue is "add helper + migrate one site," do not migrate the other sites even if they're obvious.
- **Do not skip the red step.** TDD means write the test first. If you write implementation before the test, you're not doing TDD.
- **Run the full test suite.** Do not run only the new tests. The integration and contract tests are the regression guard.
- **Do not push automatically.** Commit only. The user decides when to push (use `/push-to-github` or manual `git push`).
- **If the issue is human-in-the-loop, refuse.** This workflow is for AFK issues only. If the issue type is `human-in-the-loop`, tell the user to implement it themselves or split it into AFK sub-issues.

## Notes on the full Ralph (parallel version)

The full `/ralph` workflow from Matt's talk assumes:
- Docker sandboxing for safe parallel execution
- Git worktrees for isolated branches
- A planner agent to schedule work
- A merger agent to integrate results

Your repo does not have this infrastructure yet. This manual sequential version is the fallback. If you add Docker/worktrees later, this workflow can be extended to support a true AFK loop that picks the next unblocked issue automatically.
