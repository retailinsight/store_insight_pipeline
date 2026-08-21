# TypeScript Standards

## Type Safety

- `strict: true` is the target — current `tsconfig.json` has it disabled; new code should still be written as if strict were on, and the config should be tightened incrementally
- Never use `any`. If a value is truly unknown, use `unknown` and narrow it
- Never use non-null assertion (`!`) to silence the compiler — narrow instead
- Use `as` only at trusted boundaries (DOM queries, validated parsers)
- Type every component prop, hook return, thunk argument, and API response
- Type Redux state, dispatch, and selectors via `useAppSelector` / `useAppDispatch`

## `interface` vs `type`

- `interface` for object shapes that may be extended
- `type` for unions, intersections, mapped types, and primitive aliases

```ts
interface User {
  id: string;
  name: string;
}

type Status = "idle" | "loading" | "success" | "error";
```

## Utility Types

Prefer built-ins over hand-rolled equivalents:

- `Partial<T>`, `Required<T>`, `Readonly<T>`
- `Pick<T, K>`, `Omit<T, K>`
- `Record<K, V>`
- `ReturnType<typeof fn>`, `Awaited<T>`

## Discriminated Unions

Model state machines with a discriminant:

```ts
type FetchState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: string };
```

## Runtime Validation

- Use `zod` to validate untrusted input (API responses, URL params, forms)
- Derive TS types from schemas with `z.infer<typeof Schema>` — single source of truth

## File Conventions

Types may live in:

- Co-located with their consumer (small, single-use)
- `*.types.ts` next to the feature (shared across that feature)
- `src/models/` for domain types used across the app

## Imports

- Use `import type { ... }` for type-only imports to keep runtime bundles lean

## Validation

Always verify after changes:

```bash
npm run typecheck
```

Expected: `0 errors`.

## ESM Compatibility

This project is `"type": "module"`. In any Node-side script:

```ts
const __dirname = import.meta.dirname;
```

Do not use CommonJS `__dirname` or `require`.
