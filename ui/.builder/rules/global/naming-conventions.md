# Naming Conventions

## Files

| Kind            | Pattern                | Example                |
| --------------- | ---------------------- | ---------------------- |
| Component       | `PascalCase.tsx`       | `KpiWidget.tsx`        |
| Page            | `PascalCase.tsx`       | `SmartActionsPage.tsx` |
| Hook            | `useCamelCase.ts`      | `useMobile.ts`         |
| Utility / lib   | `camelCase.ts`         | `formatting.ts`        |
| Redux slice     | `camelCaseSlice.ts`    | `authSlice.ts`         |
| Types           | `feature.types.ts`     | `kpi.types.ts`         |
| Test            | `*.spec.ts(x)`         | `utils.spec.ts`        |
| Context         | `PascalCaseContext.tsx`| `SmartActionsContext.tsx` |

## Examples

Correct:

```text
useMobile.ts
KpiWidget.tsx
authSlice.ts
formatting.ts
```

Incorrect:

```text
use-mobile.ts
kpi-widget.tsx
Auth_Slice.ts
```

## Folders

- Use lowercase, plural where it makes sense (`components/`, `pages/`, `hooks/`)
- Group by feature when a feature owns 3+ files
- No abbreviations unless industry-standard (`api`, `ui`, `kpi`)

## Symbols

- Components & types: `PascalCase`
- Functions, variables, hooks: `camelCase`
- Constants: `SCREAMING_SNAKE_CASE` for true constants only (e.g. `MAX_RETRIES`)
- Booleans: prefix with `is`/`has`/`should` (`isLoading`, `hasError`)
- Event handlers: `handleX` for the impl, `onX` for the prop
- Async thunks: verb-based (`fetchKpis`, `completeAction`)

## Exports

- Default export: only for top-level page/route components
- Everything else: named exports
- Re-export through `index.ts` barrels only when it adds clarity (e.g. `routes/index.ts`)
