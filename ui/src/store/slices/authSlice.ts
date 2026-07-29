import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { jwtDecode } from "jwt-decode";
import { AuthUser, DecodedToken, Store } from "@/models";
import { getErrorMessage } from "@/utils/helpers/errorMessage";
import { postToken } from "@/services/authService";
import { fetchStores } from "@/services/storesService";
import { consumeState } from "@/utils/auth/oauthFlow";
import {
  getAccessTokenFromLocalStorage,
  loadStoreSelection,
  removeAuthTokenValuesFromLocalStorage,
  saveStoreSelection,
  setAuthTokenValuesInLocalStorage,
} from "@/utils/auth/localStorageAuthHelper";
import type { RootState } from "@/store";

const MS_ROLE_CLAIM =
  "http://schemas.microsoft.com/ws/2008/06/identity/claims/role";

function mapDecodedTokenToAuthUser(decoded: DecodedToken): AuthUser {
  const rawRoles =
    decoded.roles ?? (decoded as Record<string, unknown>)[MS_ROLE_CLAIM];
  const roles: string[] = Array.isArray(rawRoles)
    ? (rawRoles as string[])
    : rawRoles != null
      ? [String(rawRoles)]
      : [];

  return {
    id: String(decoded.userId ?? decoded.sub ?? decoded.id ?? ""),
    username: String(
      decoded.username ??
        decoded.preferred_username ??
        decoded.name ??
        decoded.email ??
        decoded.userId ??
        "",
    ),
    role: roles[0] ?? "",
    roleId: Number(decoded.userType ?? decoded.roleId ?? 0),
    storeId: Number(decoded.storeId ?? decoded.storeId ?? 0),
    store: decoded.store,
    stores:
      Array.isArray(decoded.stores) && decoded.stores.length > 0
        ? decoded.stores
        : decoded.store
          ? [decoded.store as Store]
          : [],
    features: Array.isArray(decoded.features) ? decoded.features : [],
  };
}

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  isTokenValid: boolean;
  token: string | null;
  decodedToken: DecodedToken | null;
  permissions: string[];
  user: AuthUser | null;
  error: string | null;
  selectedStore: Store | null;
  availableStores: Store[];
}

const storedAuth = getAccessTokenFromLocalStorage();
const storedStores = storedAuth.token
  ? loadStoreSelection()
  : { selectedStore: null, availableStores: [] as Store[] };

const initialState: AuthState = {
  isAuthenticated: !!storedAuth.token,
  isLoading: true,
  isTokenValid: !!storedAuth.token,
  token: storedAuth.token,
  decodedToken: storedAuth.decodedToken as DecodedToken | null,
  permissions: storedAuth.permissions,
  user: null,
  error: null,
  selectedStore: storedStores.selectedStore,
  availableStores: storedStores.availableStores,
};

function resetAuthState(state: AuthState): void {
  removeAuthTokenValuesFromLocalStorage();
  saveStoreSelection(null, []);
  state.isAuthenticated = false;
  state.isTokenValid = false;
  state.token = null;
  state.decodedToken = null;
  state.permissions = [];
  state.user = null;
  state.selectedStore = null;
  state.availableStores = [];
  state.error = null;
}

interface AuthorizeResult {
  token: string;
  decodedToken: DecodedToken;
  permissions: string[];
  user: AuthUser;
  selectedStore: Store | null;
  availableStores: Store[];
}

interface FetchStoresResult {
  stores: Store[];
  selectedStore: Store | null;
}

export const fetchStoresThunk = createAsyncThunk<
  FetchStoresResult,
  void,
  { rejectValue: string; state: RootState }
>("auth/fetchStores", async (_, { rejectWithValue, getState }) => {
  try {
    const stores = await fetchStores();
    const current = getState().auth.selectedStore;
    const selectedStore =
      current && stores.some((s) => s.id === current.id)
        ? current
        : (stores[0] ?? null);
    return { stores, selectedStore };
  } catch (error) {
    return rejectWithValue(getErrorMessage(error));
  }
});

export const authorize = createAsyncThunk<
  AuthorizeResult,
  { code: string; state: string },
  { rejectValue: string }
>("auth/authorize", async ({ code, state }, { rejectWithValue }) => {
  try {
    const storedState = consumeState();
    if (!storedState || state !== storedState) {
      throw new Error("Invalid OAuth session. Please try logging in again.");
    }

    const { access_token: token, refresh_token: refreshToken } =
      await postToken(code);
    const decodedToken = jwtDecode<DecodedToken>(token);
    const permissions = Array.isArray(decodedToken.features)
      ? decodedToken.features
      : [];
    const user = mapDecodedTokenToAuthUser(decodedToken);
    const selectedStore = user.stores[0] ?? null;

    setAuthTokenValuesInLocalStorage({
      token,
      refreshToken,
      decodedToken: decodedToken as Record<string, unknown>,
      permissions,
    });
    saveStoreSelection(selectedStore, user.stores);

    return {
      token,
      decodedToken,
      permissions,
      user,
      selectedStore,
      availableStores: user.stores,
    };
  } catch (error) {
    return rejectWithValue(getErrorMessage(error));
  }
});

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    initAuth(state) {
      state.isLoading = false;
      const stored = getAccessTokenFromLocalStorage();
      if (stored.token) {
        const { selectedStore, availableStores } = loadStoreSelection();
        state.token = stored.token;
        state.decodedToken = stored.decodedToken as DecodedToken | null;
        state.permissions = stored.permissions;
        state.isTokenValid = true;
        state.isAuthenticated = true;
        state.selectedStore = selectedStore;
        state.availableStores = availableStores;
      } else {
        state.isAuthenticated = false;
        state.isTokenValid = false;
      }
    },
    setTokenValid(state, action: PayloadAction<boolean>) {
      state.isTokenValid = action.payload;
    },
    logout(state) {
      resetAuthState(state);
    },
    sessionExpired(state) {
      resetAuthState(state);
    },
    selectStore(state, action: PayloadAction<Store>) {
      state.selectedStore = action.payload;
      saveStoreSelection(action.payload, state.availableStores);
    },
    clearError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(authorize.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(authorize.fulfilled, (state, { payload }) => {
        state.isLoading = false;
        state.isAuthenticated = true;
        state.isTokenValid = true;
        state.token = payload.token;
        state.decodedToken = payload.decodedToken;
        state.permissions = payload.permissions;
        state.user = payload.user;
        state.selectedStore = payload.selectedStore;
        state.availableStores = payload.availableStores;
        state.error = null;
      })
      .addCase(authorize.rejected, (state, { payload }) => {
        state.isLoading = false;
        state.isAuthenticated = false;
        state.isTokenValid = false;
        state.error = payload ?? "Authentication failed.";
      })
      .addCase(fetchStoresThunk.fulfilled, (state, { payload }) => {
        state.availableStores = payload.stores;
        state.selectedStore = payload.selectedStore;
        saveStoreSelection(payload.selectedStore, payload.stores);
      });
  },
});

export const {
  initAuth,
  setTokenValid,
  logout,
  sessionExpired,
  selectStore,
  clearError,
} = authSlice.actions;

export default authSlice.reducer;
