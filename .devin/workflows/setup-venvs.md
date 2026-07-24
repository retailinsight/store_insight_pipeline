---
description: Create per-service Python venvs and install dependencies (idempotent first-time setup)
---

Creates a dedicated `.venv` for each Python service in the repo and installs
its `requirements.txt`. Also (re)builds the shared `.venv-experiments` used
for notebooks, the pipeline test suite, and ad-hoc experiments.

Per-service venvs are required because services pin conflicting versions
(e.g. `pipeline_ui/backend` pins `pydantic==2.7.1` but `mcp/` needs
`pydantic>=2.11`). Sharing one venv across them breaks installs.

**This workflow is idempotent**: if a `.venv` already exists it is left
alone. Pass an explicit instruction like "rebuild the mcp venv" to force a
specific service to be recreated.

## Layout produced

```
store_insight/
  .venv-experiments/                    # shared dev/notebook env (requirements-dev.txt)
  api2/.venv/                           # api2 service
  mcp/.venv/                            # mcp server
  pipeline_ui/backend/.venv/            # pipeline experiments backend
```

`.gitignore` already excludes `.venv/` and `.venv-*/`.

## Prerequisites

- Python 3.12 on PATH as `py -3.12`
- The repo cloned at `c:\Users\DanielTaylor\StoreInsight\store_insight`

## Steps

For each of the following four targets, do the venv block below. If a
target's `.venv` directory already exists, skip it (report "already
present"). Run them sequentially, not in parallel, so pip output stays
readable.

Targets:
1. `c:\Users\DanielTaylor\StoreInsight\store_insight\api2` — `requirements.txt`
2. `c:\Users\DanielTaylor\StoreInsight\store_insight\mcp` — `requirements.txt`
3. `c:\Users\DanielTaylor\StoreInsight\store_insight\pipeline_ui\backend` — `requirements.txt`
4. `c:\Users\DanielTaylor\StoreInsight\store_insight` — `requirements-dev.txt` into `.venv-experiments`

### Per-target venv block

For targets 1–3 (each service uses `.venv`):

```powershell
# Cwd: <target dir>
if (-not (Test-Path .venv)) {
  py -3.12 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --upgrade pip
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
} else {
  Write-Host ".venv already exists in <target> — skipping."
}
```
// turbo

For target 4 (root, uses `.venv-experiments`):

```powershell
# Cwd: c:\Users\DanielTaylor\StoreInsight\store_insight
if (-not (Test-Path .venv-experiments)) {
  py -3.12 -m venv .venv-experiments
  .\.venv-experiments\Scripts\python.exe -m pip install --upgrade pip
  .\.venv-experiments\Scripts\python.exe -m pip install -r requirements-dev.txt
} else {
  Write-Host ".venv-experiments already exists — skipping."
}
```
// turbo

## Forcing a rebuild of a specific venv

If the user asks to rebuild a specific venv (e.g. because deps got
corrupted), run for that one target only:

```powershell
# Cwd: <target dir>
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Before deleting, confirm no process is using the venv (no live uvicorn
running from it). If one is, ask the user to stop it first.

## Verification

After all four are created, sanity-check by running each interpreter:

```powershell
.\api2\.venv\Scripts\python.exe -c "import fastapi, snowflake.snowpark; print('api2 ok')"
.\mcp\.venv\Scripts\python.exe -c "import mcp, snowflake.snowpark, psycopg; print('mcp ok')"
.\pipeline_ui\backend\.venv\Scripts\python.exe -c "import fastapi, snowflake.snowpark; print('pipeline_ui ok')"
.\.venv-experiments\Scripts\python.exe -c "import pytest, ruff, snowflake.snowpark; print('experiments ok')"
```
// turbo

The last `import ruff` may fail (ruff is a CLI, not always importable);
if so, run `.\.venv-experiments\Scripts\ruff.exe --version` instead.

## Reporting

Report a one-line status per target, e.g.:

```
api2/.venv:                created (12 packages)
mcp/.venv:                 already present — skipped
pipeline_ui/backend/.venv: created (15 packages)
.venv-experiments:         created (8 packages)
```
