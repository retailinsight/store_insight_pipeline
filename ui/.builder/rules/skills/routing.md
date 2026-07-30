# Routing Standards

## Library

React Router 6 (`react-router-dom`) in SPA mode.

## Structure

```text
src/routes/
 ├── AppRoutes.tsx       # all <Route> definitions
 ├── ProtectedRoute.tsx  # auth guard wrapper
 └── index.ts            # barrel
```

## Rules

- All `<Route>` definitions live in `AppRoutes.tsx` — never inline in `App.tsx` or pages
- `App.tsx` only renders `<BrowserRouter>` + providers + `<AppRoutes />`
- Catch-all `*` route mounts `NotFound` and must be the last route
- Protected sections wrap children with `<ProtectedRoute>`
- Use `useNavigate`/`<Link>`/`<Navigate>` — never `window.location.href` for in-app navigation

## Route Naming

- Lowercase kebab-case URLs: `/smart-actions`, `/successes`
- Dynamic segments: `:id` (typed via `useParams<{ id: string }>()`)
- Avoid trailing slashes

## Code Splitting

Lazy-load heavy or rarely-visited pages:

```tsx
const SmartActionsPage = lazy(() => import("@/pages/SmartActionsPage"));

<Route
  path="/smart-actions"
  element={
    <Suspense fallback={<PageSkeleton />}>
      <SmartActionsPage />
    </Suspense>
  }
/>;
```

## Guards

- `ProtectedRoute` reads auth state from Redux (not localStorage directly)
- Preserve the originally requested path with `state={{ from: location }}` for post-login redirect
- Show a loader while auth is rehydrating — never flash the login page

## Search Params & State

- Use `useSearchParams` for URL-driven UI state
- Use `useLocation().state` for short-lived navigation payloads — don't rely on it for refresh-survivable data
