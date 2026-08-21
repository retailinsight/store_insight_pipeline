# Authentication Standards

## Overview

OAuth2 Authorization Code flow (no PKCE). All auth logic is centralized:

| Concern | File |
|---|---|
| OAuth endpoints config | `utils/auth/oauthConfig.ts` |
| Login / logout redirects | `utils/auth/oauthFlow.ts` |
| All auth storage | `utils/auth/localStorageAuthHelper.ts` |
| Raw token read for axios | `utils/auth/tokenStorage.ts` |
| Session expiry bridge | `utils/auth/sessionHandler.ts` |
| Auth Redux state | `store/slices/authSlice.ts` |
| App boot initialization | `store/AuthInitializer.tsx` |
| Token exchange HTTP call | `services/authService.ts` |

## OAuth Flow

1. `initiateLogin(returnTo)` — generates CSRF `state`, stores it + `returnTo` in `sessionStorage`, redirects to auth server
2. Auth server redirects back to `/auth/callback?code=…&state=…`
3. `AuthCallback` page dispatches `authorize({ code, state })`
4. `authorize` thunk:
   - Validates CSRF state via `consumeState()`
   - Calls `postToken(code)` from `services/authService.ts`
   - Decodes JWT with `jwtDecode<DecodedToken>(token)`
   - Extracts `features[]` (permissions) from decoded payload
   - Persists via `setAuthTokenValuesInLocalStorage` and `saveStoreSelection`
   - Hydrates Redux: `token`, `decodedToken`, `permissions`, `user`, `selectedStore`
5. `AuthCallback` navigates to `consumeReturnTo()`, optionally branching on `result.permissions`

## Token Storage (`localStorageAuthHelper.ts`)

| Key | Value |
|---|---|
| `STORE_INSIGHT_ACCESS_TOKEN` | Raw JWT — read by axios request interceptor |
| `STORE_INSIGHT_REFRESH_TOKEN` | Refresh token (when present) |
| `STORE_INSIGHT_DECODED_TOKEN` | JSON-serialized JWT payload |
| `STORE_INSIGHT_PERMISSIONS` | JSON-serialized `features[]` array |
| `STORE_INSIGHT_SELECTED_STORE` | Active store object |
| `STORE_INSIGHT_AVAILABLE_STORES` | All user stores array |

- `localStorageAuthHelper.ts` is the single source of truth for all auth storage
- `tokenStorage.ts` provides `getAccessToken()` only for the axios interceptor
- Never log tokens or embed them in URLs

## Session Handling

On 401 from `apiInstance.ts` response interceptor:

1. `removeAuthTokenValuesFromLocalStorage()` — clears all auth localStorage keys
2. `handleSessionExpired()` — invokes the registered callback
3. Registered callback (in `AuthInitializer.tsx`) dispatches `sessionExpired`, clears data slices, shows a toast, then calls `initiateLogin("/")` after a short delay

## Routing

- Wrap private routes with `ProtectedRoute` from `src/routes/ProtectedRoute.tsx`
- `ProtectedRoute` reads `isAuthenticated` from Redux — never from localStorage directly
- Unauthenticated access calls `initiateLogin(location.pathname + location.search)` to preserve the intended path

## Security

- Always send credentials over HTTPS
- CSRF `state` token validated on every callback — never skip
- Do not trust client-side role/feature checks alone — server must re-authorize
- Sanitize any user-rendered profile fields (name, avatar URL)
