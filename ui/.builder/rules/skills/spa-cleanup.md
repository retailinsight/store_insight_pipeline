# SPA Cleanup Standards

This project is a frontend-only SPA. Apply these rules when starting from the Fusion Starter or any template that ships server scaffolding.

## Remove

```text
server/
netlify/functions/
vite.config.server.ts
```

Also remove from `package.json`:

- Express, CORS, body-parser, and other server-only dependencies
- `start` / `start:server` scripts that boot Express
- Server-only build steps

## Configuration Cleanup

- Delete unused `vite.config.ts` proxy entries
- Delete `netlify.toml` redirects that target serverless functions you removed
- Keep a single SPA fallback redirect (`/* → /index.html 200`)

## Keep

- `src/models/` — TypeScript type definitions for the app
- `vite.config.ts` — frontend-only config
- One deployment target (Netlify or Vercel) configured for SPA fallback

## Verification

After cleanup:

```bash
npm run typecheck
npm run build
npm run dev
```

All must succeed with no references to removed server modules.

## Goal

A lean, frontend-only SPA with no dead backend scaffolding, no unused dependencies, and a clean dependency graph.
