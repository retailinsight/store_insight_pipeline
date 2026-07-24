---
description: Start the Pipeline Experiments app (pipeline_ui backend on :8002 + frontend on :8081)
---

Spins up the `pipeline_ui/` experimentation app — a stateless workbench for
tweaking detector / gatherer / skill config and re-running the pipeline
against Snowflake.

## Prerequisites (check once per machine)

- `pipeline_ui\backend\.env` exists with valid Snowflake creds (copy from
  `pipeline_ui\backend\.env.example`).
- `pipeline_ui\backend\.venv` exists with deps installed. If missing, run
  the `/setup-venvs` workflow or:
  ```
  py -3.12 -m venv pipeline_ui\backend\.venv
  pipeline_ui\backend\.venv\Scripts\python.exe -m pip install -r pipeline_ui\backend\requirements.txt
  ```
- Frontend node_modules installed: `npm install` inside `pipeline_ui\frontend\`.

If any prerequisite is missing, stop and tell the user what to fix.

## Steps

1. Check no process is already bound to ports 8002 (backend) or 8081
   (frontend).
   // turbo
   ```
   netstat -ano | findstr "LISTENING" | findstr ":8002 :8081"
   ```
   If either port is in use, identify the PID and ask the user before
   killing it. If it is already a healthy instance of this app
   (GET /health on 8002 returns 200, frontend reachable on 8081), skip
   straight to step 4.

2. Start the backend in a non-blocking background terminal.
   - Command: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002`
   - Cwd: `c:\Users\DanielTaylor\StoreInsight\store_insight\pipeline_ui\backend`
   - Blocking: false
   - WaitMsBeforeAsync: 4000
   // turbo

   Wait ~4s, then check the terminal output. Confirm:
   - "Uvicorn running on http://127.0.0.1:8002" is present.
   - No import errors or Snowflake connection tracebacks.

   If there are real errors, surface the output and stop.

3. Start the frontend in a separate non-blocking background terminal.
   - Command: `npm run dev`
   - Cwd: `c:\Users\DanielTaylor\StoreInsight\store_insight\pipeline_ui\frontend`
   - Blocking: false
   - WaitMsBeforeAsync: 4000
   // turbo

   Wait ~4s and confirm Vite prints a "Local:  http://localhost:8081/"
   line. If a different port is shown (e.g. Vite picked 8082 because 8081
   was busy), surface that to the user.

4. Verify the backend health endpoint:
   // turbo
   ```
   curl.exe -s http://localhost:8002/health
   ```
   Expected: `{"status":"ok"}`. If not, surface the error and stop.

5. Open a browser preview for the frontend at `http://localhost:8081` so
   the user can click through to it.

6. Report to the user:

   ```
   Pipeline Experiments app:
     Backend:   http://localhost:8002  (health ✓)
     Frontend:  http://localhost:8081
     Docs:      http://localhost:8002/docs

   Background command IDs:
     backend:  <id>
     frontend: <id>

   Stop with: kill those two background terminals.
   ```

## Stopping

Terminate the two background terminals started in steps 2 and 3. Do not
`taskkill` blindly — it may hit unrelated Python/Node processes.
