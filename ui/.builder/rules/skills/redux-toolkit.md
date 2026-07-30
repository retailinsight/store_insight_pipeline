# Redux Toolkit Standards

## Store Structure

```text
src/store/
 ├── index.ts            # configureStore + RootState/AppDispatch types
 ├── hooks.ts            # useAppDispatch + useAppSelector
 ├── AuthInitializer.tsx # bootstraps auth on app mount
 └── slices/
     ├── authSlice.ts
     ├── kpisSlice.ts
     ├── successesSlice.ts
     └── actionsSlice.ts
```

Thunks call functions from `src/services/` — no direct HTTP in slice files.

## Rules

- Always `configureStore` (never raw `createStore`)
- Export typed hooks; components must use them, never the raw `useDispatch`/`useSelector`
- Async work goes in `createAsyncThunk` — components never call axios or fetch directly
- Reducers must be pure and synchronous (Immer drafts are fine)
- Never mutate state outside a `createSlice` reducer
- Keep slice files cohesive — one feature per slice

## Typed Hooks

```ts
// store/hooks.ts
import { useDispatch, useSelector, type TypedUseSelectorHook } from "react-redux";
import type { RootState, AppDispatch } from "./index";

export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
```

## Slice Shape

Each slice typically manages:

```ts
interface FeatureState {
  data: Feature[];
  status: "idle" | "loading" | "success" | "error";
  error: string | null;
}
```

Prefer a `status` enum over a boolean `loading` flag to make UI state exhaustive.

## Async Thunks

- Always type the thunk: `createAsyncThunk<Returned, Arg, { rejectValue: string }>`
- Use `rejectWithValue(getErrorMessage(err))` — never throw raw errors
- Handle `pending` / `fulfilled` / `rejected` in `extraReducers` using the builder callback form
- Use `.unwrap()` in components only when you need to chain on success/failure
- HTTP calls go in `src/services/` and are imported into the thunk

## Selectors

- Co-locate basic selectors with the slice (`selectKpis`, `selectKpisStatus`)
- Use `createSelector` (Reselect, included with RTK) for derived/expensive computations
- Selectors must be pure and independent of component props (or use the curried form)

## Performance

- Select the smallest slice of state needed — avoid `useAppSelector(s => s)`
- Memoize derived arrays/objects with `createSelector` to keep referential equality
- Do not store derivable data in Redux (compute it via selectors)

## Persistence

- Persist only what survives a refresh (auth tokens, user preferences)
- Auth data is persisted via `utils/auth/localStorageAuthHelper.ts` — not raw localStorage in slices
- Never persist transient `loading`/`error` flags
