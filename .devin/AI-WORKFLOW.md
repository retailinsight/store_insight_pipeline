# AI Feature Workflow — How to Use It

A four-stage pipeline for taking a feature idea from "vague Slack message" to "merged code", borrowed from Matt Pocock's RWX 2026 workshop and adapted for this repo.

The whole thing is built around two LLM constraints:

1. **Smart zone vs. dumb zone.** LLMs degrade as their context fills up (~100K tokens is roughly where things start to get dumber, regardless of the advertised window size). Keep tasks small enough to fit in the smart zone.
2. **Memento problem.** Every fresh chat starts from the same blank state. Build artifacts (PRDs, issue files) that survive context resets, instead of relying on long compacted conversations.

The workflow optimizes for both: it generates **assets** (chat history → PRD → issues) so each later stage starts from a clean context with only what it needs.

---

## The four workflows

| Stage | Workflow | Output | Context discipline |
|-------|----------|--------|--------------------|
| 1. Align | `/grill-me` | Chat history (no file) | Fresh chat. **Human in the loop.** |
| 2. Capture destination | `/write-prd` | `prds/<slug>/PRD.md` | Same chat as the grill. Human in the loop. |
| 3. Plan journey | `/prd-to-issues` | `prds/<slug>/01-*.md`, `02-*.md`, … | **New chat.** Human-reviewed. |
| 4. Execute | (manual: pick an issue, implement) | Code + tests + commits | New chat per issue. **Mostly AFK.** |

Plus one orthogonal workflow:

- `/improve-architecture` — scans a target area for shallow-module smells and recommends deepening. Recommendations only, no edits. Run independently whenever a part of the codebase feels hard to work in.

---

## Stage 1 — `/grill-me`

**When:** You have a feature idea, a Slack message from a stakeholder, or a vague problem statement.

**What it does:** Interviews you one question at a time, with a recommended answer for each, walking the design tree (data model → behavior → API → UI → edge cases → out-of-scope). Explores the codebase silently to ground its recommendations.

**Usage:**

```
/grill-me <paste the idea or pass a path to a brief>
```

**Posture during the grill:**

- Answer one question at a time. Short answers are fine — "agree" / "yes" / "skip" / "no, do X instead".
- If you don't know the answer, say so — that's a flag that you need to pull in a teammate or a domain expert.
- The chat history *is* the deliverable. Don't try to summarize as you go.

**Stop when:** All major decision branches have an answer, or you say "stop" / "let's wrap" / "I'm good".

---

## Stage 2 — `/write-prd`

**When:** Right after the grill, in the **same chat**.

**What it does:** Writes `prds/<slug>/PRD.md` with: Problem, Solution, User Stories, Module Map, Implementation Decisions, Testing Decisions, Out of Scope.

**Usage:**

```
/write-prd
```

**Posture:**

- The agent will propose a **module map** before writing the file. **Look at this.** It's the bridge between the design concept and code, and it's where your eyeballs add the most value.
- Don't read the resulting PRD line-by-line. You already aligned during the grill. Skim Out of Scope to make sure nothing important got dropped.
- If the grilling was thin, the agent will ask follow-up questions before writing.

---

## Stage 3 — `/prd-to-issues`

**When:** PRD is written. **Start a new chat** (clean context — the PRD is now the source of truth, not the chat history).

**What it does:** Splits the PRD into a canban board of issue files in `prds/<slug>/`, with explicit `Blocked by:` / `Blocks:` relationships and `AFK` / `human-in-the-loop` tags. Optimizes for **vertical slices** — each issue produces something visible end-to-end.

**Usage:**

```
/prd-to-issues prds/<slug>/PRD.md
```

**Posture:**

- The agent will propose a slice list before writing files. **Push back if the first slice is horizontal** ("all the schema changes"). Demand a thin end-to-end slice that produces something visible by the end of issue #1.
- Independently grabbable: each issue should be completable by a single agent in one session.
- The canban shape is what enables parallelism later. A linear list of phases is *worse* than a DAG, even if the DAG looks more complex.

---

## Stage 4 — Execute issues

**When:** Issue board is ready.

**No workflow yet for this stage in our setup** — Matt's `/ralph` AFK loop needs Docker sandboxing and git worktrees we haven't set up. For now: pick an unblocked issue, start a new chat, paste the issue file, and ask the agent to implement it using TDD (red → green → refactor) and to run feedback loops (tests + types) before declaring done.

A future `/ralph` workflow can automate this once we decide on a sandboxing approach.

**Posture:**

- One issue per chat. New chat for the next issue.
- Watch the token counter. If you cross ~100K, stop and start over with a tighter scope.
- Code review the result. Don't read the agent's PRD-summary checklist; read the actual diff.
- QA the running app, not just the test output. QA is where your taste re-enters the loop.

---

## `/improve-architecture` (orthogonal)

**When:** A part of the codebase feels hard to work in, hard to test, or AI keeps producing slop in it.

**What it does:** Scans a target area, identifies shallow-module clusters and weak test seams, proposes deeper-module shapes. Output is a chat-only ranked list of candidates. **No code edits.**

**Usage:**

```
/improve-architecture pipeline/stages/_2_score/
```

If you act on a recommendation, that becomes a new PRD (`/write-prd`) or a new issue on an existing board.

---

## Where files live

```
prds/
└── <feature-slug>/
    ├── PRD.md            ← from /write-prd
    ├── 01-<slug>.md      ← from /prd-to-issues
    ├── 02-<slug>.md
    └── ...
```

This is separate from the **ideas box** (the MCP-backed triage queue used by `/process-ideas`). Ideas are raw, undecided. PRDs are decided features being broken down for execution.

---

## Quick reference card

```
new feature idea
        │
        ▼
   /grill-me                    ← fresh chat, one question at a time
        │
        ▼
   /write-prd                   ← same chat; review the module map
        │
        ▼  (start new chat)
   /prd-to-issues               ← review the slice list before files are written
        │
        ▼  (one new chat per issue)
   implement → test → commit    ← TDD, run feedback loops, QA the running app
        │
        ▼
        PR
```

Anywhere in the loop, if a codebase area feels rotten:

```
/improve-architecture <path>kwargs-filtering logic gets one place to live, one test, one bug surface.
```

---

## Anti-patterns to avoid

- **Reading the PRD line-by-line after writing it.** You aligned during the grill. Trust the summary.
- **Horizontal phases.** "Phase 1 = all the schemas; Phase 2 = all the APIs." No feedback until phase 3. Use vertical slices.
- **Long single chats.** When a chat crosses ~100K tokens, output starts degrading fast. Start a new chat with a fresh prompt and the relevant artifact.
- **Compacting instead of clearing.** Compacted history accumulates sediment. Prefer building durable artifacts (PRDs, issues) and clearing.
- **Specs-to-code without looking at the code.** The code is the battleground. Keep the module map alive in your head and review the diff, not just the agent's self-report.
- **Automating QA away.** QA is where your taste re-enters. Click the running app.
