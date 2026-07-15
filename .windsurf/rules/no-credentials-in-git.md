---
trigger: always_on
---

# Never push credentials to git

Credentials, tokens, passwords, and private keys must NEVER be committed or pushed to git.

## What counts as a credential
- Snowflake PAT tokens (JWT-like strings starting with `eyJ`), passwords, OAuth tokens
- Private keys (`*.p8`, `*.pem`, `*.key`, `rsa_key*`)
- API keys of any kind (OpenAI, Anthropic, cloud providers, etc.)
- Any `.env` file with real values (only `.env.example` with placeholders is allowed)

## Rules
1. Real credentials live ONLY in gitignored files: `.env`, `.local/credentials/snowflake_credentials.py`, `pipeline/.env`, or `working_snowflake_config.env`. Never hardcode them in scripts, notebooks, docs, or config committed to git.
2. Scripts and notebooks must load credentials through the gitignored root compatibility loader (`from snowflake_credentials import get_credentials`) or from environment variables / `.env` — never inline literals.
3. Before any `git add` / `git commit` / `git push`, scan staged content for secrets (e.g. `git diff --cached | Select-String -Pattern "eyJ|BEGIN.*PRIVATE KEY|SNOWFLAKE_PASSWORD=(?!your-|<)"`). If anything matches, STOP and remove the secret before committing.
4. When creating a new credential-bearing file, immediately add it to `.gitignore` BEFORE writing the secret into it, and verify with `git check-ignore <file>`.
5. If a secret is ever committed, treat it as compromised: rotate it with the Snowflake admin and rewrite history — do not just delete the file in a follow-up commit.
6. Never print full tokens in terminal output, logs, or chat; refer to them by file location instead.
