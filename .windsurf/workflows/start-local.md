---
description: Start the Store Insight API (api2) and UI locally in parallel
---

Spin up both the FastAPI backend (`api2/`) and the Vite front end (`ui/`) in
separate background terminals so they can be used together for local dev.

## Prerequisites (check once per machine)

- `api2\.env` exists and contains valid Snowflake service-account credentials
  (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_B64`,
  `STORE_INSIGHT_API_KEY`, etc.).
- Python deps installed: `pip install -r api2\requirements.txt`
- Node deps installed: `npm install` inside `ui\`

If any prerequisite is missing, stop and fix it before running the steps below.

## Steps

1. Check no process is already bound to ports 8000 (API) or 8080 (UI). If one
   is, either reuse it or ask the user before killing it.
   // turbo

2. Start the API in a non-blocking background terminal.
   - Command: `uvicorn app.main:app --reload --port 8000`
   - Cwd: `c:\Users\DanielTaylor\StoreInsight\store_insight\api2`
   - Blocking: false
   - Wait ~2s after launch, then read the terminal output to confirm
     "Uvicorn running on http://127.0.0.1:8000" and no Snowflake/auth errors.
   // turbo

3. Start the UI in a separate non-blocking background terminal.
   - Command: `npm run dev`
   - Cwd: `c:\Users\DanielTaylor\StoreInsight\store_insight\ui`
   - Blocking: false
   - Wait ~2s, then read the terminal to confirm Vite prints a
     "Local:  http://localhost:8080/" line.
   // turbo

4. Open a browser preview for the UI at `http://localhost:8080` so the user
   can click through to it.

5. Report back with:
   - API URL: `http://localhost:8000` (docs at `/docs`)
   - UI URL:  `http://localhost:8080`
   - The two background terminal IDs so they can be stopped later.

## Stopping

To stop both servers, terminate the two background terminals started in
steps 2 and 3 (do not `taskkill` blindly — it may hit unrelated Python/Node
processes).
