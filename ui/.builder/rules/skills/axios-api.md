# Axios API Standards

## Required Structure

```text
src/
 ├── services/                     # HTTP fetch functions (one file per domain)
 │   ├── authService.ts            # postToken(code)
 │   ├── kpiService.ts             # fetchKpis()
 │   ├── successService.ts         # fetchSuccesses()
 │   └── actionsService.ts         # fetchActions()
 └── utils/
     ├── instance/
     │   ├── apiInstance.ts        # authenticated requests
     │   └── authAPIInstance.ts    # public auth endpoints
     ├── auth/
     │   ├── localStorageAuthHelper.ts
     │   ├── tokenStorage.ts
     │   └── sessionHandler.ts
     └── helpers/
         ├── apiBaseUrl.ts
         └── errorMessage.ts
```

## Rules

- All HTTP traffic goes through one of the two axios instances — no ad-hoc `axios.create` in components
- `postToken` in `authService.ts` uses native `fetch` (auth server → no axios interceptors involved)
- Base URL comes from `apiBaseUrl.ts` (reads `import.meta.env.VITE_API_BASE_URL`)
- Never hardcode URLs in components or thunks
- HTTP functions live in `src/services/` and are called only from `createAsyncThunk`

## Interceptors

`apiInstance.ts` request interceptor:

- Inject `Authorization: Bearer <token>` from `tokenStorage.getAccessToken()`
- Attach `Content-Type: application/json` unless `FormData`

Response interceptor:

- On 401 → `removeAuthTokenValuesFromLocalStorage()` then `handleSessionExpired()`
- On other errors → reject with the original AxiosError (normalized by `errorMessage.ts` in thunks)

## API Calls

- Components never call axios or fetch directly
- HTTP functions live in `src/services/`, called from thunks in `store/slices/`
- Thunk return types must be explicit:

```ts
export const fetchKpisThunk = createAsyncThunk<KpiData[], void, { rejectValue: string }>(
  "kpis/fetch",
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetchKpis();
      return response.data;
    } catch (err) {
      return rejectWithValue(getErrorMessage(err));
    }
  }
);
```

## Error Normalization

`errorMessage.ts` accepts `unknown` and returns `string`:

- Prefers `error.response.data.message` when present
- Falls back to `error.message`
- Falls back to a generic string

## Security

- Never log full request/response bodies in production builds
- Strip `Authorization` headers from any error logging
