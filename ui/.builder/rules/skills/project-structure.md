# Project Structure Standards

## Canonical Layout

```text
src/
 ├── components/         # Reusable UI (PascalCase)
 │   ├── ui/             # Radix + Tailwind primitives (shadcn-style)
 │   ├── icons/          # Centralized SVG/icon exports
 │   └── dialogs/        # Modal/dialog components
 ├── models/             # TypeScript interfaces and types (split by domain)
 ├── pages/              # Route-level components
 ├── routes/             # AppRoutes, ProtectedRoute, route table
 ├── services/           # HTTP fetch functions (one file per domain)
 ├── store/              # Redux Toolkit (index, hooks, AuthInitializer, slices/)
 ├── hooks/              # Reusable custom hooks
 ├── contexts/           # React contexts (low-frequency only)
 ├── lib/                # Pure utilities (formatting, cn, etc.)
 ├── utils/              # Side-effecting utilities (auth, axios, helpers)
 ├── App.tsx             # Provider + layout + route mount
 ├── global.css          # Tailwind directives + theme tokens
 └── vite-env.d.ts
```

## Rules

- Source root is `src/` (not `client/`)
- Use path alias `@/*` → `src/*`
- Group by feature once a feature owns 3+ related files
- Business logic lives in hooks, slices, or utils — never in JSX
- Barrel exports (`index.ts`) only when they reduce import noise meaningfully
- Never reach into another feature's internals — go through its public exports

## `models/`

Domain-specific TypeScript interfaces, one file per domain:

```text
src/models/
 ├── auth.ts      # Store, AuthUser, DecodedToken
 ├── kpi.ts       # KpiData, KpisResponse, …
 ├── success.ts   # SuccessData, SuccessesResponse
 ├── action.ts    # ActionData, ActionsResponse
 └── index.ts     # barrel re-export
```

- Import via `@/models` (the barrel) or a specific file
- No runtime code in model files — types and interfaces only
- Do **not** use `@shared/api` — that path no longer exists

## `services/`

Pure HTTP fetch functions, one file per domain. No Redux, no React.

```text
src/services/
 ├── authService.ts      # postToken(code)
 ├── kpiService.ts       # fetchKpis()
 ├── successService.ts   # fetchSuccesses()
 └── actionsService.ts   # fetchActions()
```

- Only functions that make HTTP calls live here
- Called exclusively from `createAsyncThunk` in `store/slices/`
- No side effects beyond the HTTP call — no localStorage, no dispatch

## `lib/` vs `utils/`

- `lib/` → pure, deterministic, side-effect-free helpers (formatters, `cn`, parsers)
- `utils/` → utilities with side effects or external dependencies (axios, storage, session)

## Centralize

- Formatting (number, currency, date) → `lib/formatting.ts`
- Class merging → `lib/utils.ts` (`cn`)
- All auth storage → `utils/auth/localStorageAuthHelper.ts`
- API base URL → `utils/helpers/apiBaseUrl.ts`

## Anti-patterns

- Deeply nested folders (> 3 levels under `src/`)
- Mixing UI primitives and feature components in the same folder
- Cross-feature imports that bypass barrels
- Utility files named `helpers.ts` / `misc.ts` / `common.ts`
- Types defined outside `src/models/` (no `shared/` folder)
