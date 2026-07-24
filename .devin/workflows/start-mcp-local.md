---
description: Start the Store Insight MCP server locally for use with Windsurf or Claude Desktop
---

Starts the MCP server (`mcp/`) on port 8001 with auth disabled so Windsurf
(and Claude Desktop) can connect to it directly without WorkOS tokens.

## Prerequisites (check once per machine)

- `mcp/.env` exists with valid Snowflake credentials (copy from `mcp/.env.example`).
- Python venv created at `mcp\.venv` with deps installed:
  ```
  py -3.12 -m venv mcp\.venv
  mcp\.venv\Scripts\python.exe -m pip install -r mcp\requirements.txt
  ```
- Postgres `DATABASE_URL` is set if you want ideas-box tools to work (optional
  for alerts-only use).

If any prerequisite is missing, stop and tell the user what to fix.

## Steps

1. Check whether port 8001 is already in use.
   // turbo
   ```
   netstat -ano | findstr :8001
   ```
   If a process is already bound to 8001, check if it is the MCP server
   (report its PID). Ask the user before killing it. If it is already the
   MCP server and healthy (GET /health returns 200), skip to step 5.

2. Create or verify `mcp/.env.local` disables auth for local dev.

   The file should contain at minimum:
   ```
   DEV_MODE=true
   MCP_RESOURCE_URL=http://localhost:8001/mcp
   ```
   `DEV_MODE=true` is the supported bypass — the auth middleware
   short-circuits all JWT validation when it's set, so an unset/blank
   `WORKOS_AUTHKIT_DOMAIN` is fine. Without `DEV_MODE`, every `/mcp`
   request returns 503 if `WORKOS_AUTHKIT_DOMAIN` is missing.

   If `mcp/.env.local` does not exist, create it with the two lines above.
   If it exists, append `DEV_MODE=true` if missing.

   IMPORTANT: never overwrite `mcp/.env` — only write to `mcp/.env.local`.
   Never set `DEV_MODE=true` in production.

3. Start the MCP server in a non-blocking background terminal.
   - Command: `.\.venv\Scripts\python.exe -m uvicorn app.server:app --reload --port 8001`
   - Cwd: `c:\Users\DanielTaylor\StoreInsight\store_insight\mcp`
   - Blocking: false
   - WaitMsBeforeAsync: 3000
   // turbo

4. Wait 3 seconds then check the terminal output. Confirm:
   - "Uvicorn running on http://127.0.0.1:8001" is present.
   - No import errors or missing-module tracebacks.
   - The two warnings about `WORKOS_AUTHKIT_DOMAIN` and `MCP_RESOURCE_URL`
     being unset are expected and acceptable for local dev — ignore them.

   If there are real errors (import failures, Snowflake connection errors),
   surface the output and stop.

5. Verify the health endpoint responds:
   // turbo
   ```
   curl -s http://localhost:8001/health
   ```
   Expected: `{"status":"ok"}`. If not, surface the error and stop.

6. Report to the user:

   ```
   MCP server running at http://localhost:8001
   MCP endpoint:  http://localhost:8001/mcp
   Health check:  http://localhost:8001/health  ✓

   Auth: DISABLED (local dev mode — no WorkOS token required)

   To connect Windsurf:
     Settings → MCP Servers → Add Server
     URL:  http://localhost:8001/mcp
     Type: streamable-http
     (no auth header needed)

   To connect Claude Desktop, add to claude_desktop_config.json:
     {
       "mcpServers": {
         "store-insight-local": {
           "url": "http://localhost:8001/mcp"
         }
       }
     }

   To stop: terminate the background terminal for the MCP server.
   ```

## Stopping

To stop the server, kill the background terminal started in step 3.
Do not use `taskkill` blindly — it may hit unrelated Python processes.
