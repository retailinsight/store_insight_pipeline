# Operational Scripts

Utility scripts for running and monitoring the Store Insight pipeline against
Snowflake. All require the company VPN (Snowflake network policy) and the
gitignored `.local/credentials/snowflake_credentials.py`. The gitignored root
`snowflake_credentials.py` is a compatibility loader, so existing imports continue to work.

Run from the repo root:

```
python scripts/<script>.py
```

| Script | Purpose |
|---|---|
| `test_pat_connection.py` | Verify Snowflake connectivity with the `SVC_STOREINSIGHT` PAT credentials. Run this first when debugging access issues. |
| `check_run_progress.py` | Show the most recent Snowflake queries for the service account — use to monitor a pipeline run in flight. |
| `check_cortex_count.py` | Count successful Cortex COMPLETE calls in the current run and estimate remaining time for the narrative stage. |
| `check_cortex_models.py` | Test which Cortex LLM models are available on the account (used when `mistral-large` was deprecated 2026-07-08). |

Historical one-off connection/SSO debug scripts live in `archive/connection_debug/`
(gitignored, kept locally for reference).
