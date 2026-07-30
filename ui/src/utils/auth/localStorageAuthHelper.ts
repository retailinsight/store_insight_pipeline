import type { Store } from "@/models";

const ACCESS_TOKEN_KEY = "STORE_INSIGHT_ACCESS_TOKEN";
const REFRESH_TOKEN_KEY = "STORE_INSIGHT_REFRESH_TOKEN";
const DECODED_TOKEN_KEY = "STORE_INSIGHT_DECODED_TOKEN";
const PERMISSIONS_KEY = "STORE_INSIGHT_PERMISSIONS";
const SELECTED_STORE_KEY = "STORE_INSIGHT_SELECTED_STORE";
const AVAILABLE_STORES_KEY = "STORE_INSIGHT_AVAILABLE_STORES";

export interface StoredAuthData {
  token: string | null;
  decodedToken: Record<string, unknown> | null;
  permissions: string[];
}

export interface StoredStoreData {
  selectedStore: Store | null;
  availableStores: Store[];
}

export function getAccessTokenFromLocalStorage(): StoredAuthData {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  const decodedRaw = localStorage.getItem(DECODED_TOKEN_KEY);
  const permissionsRaw = localStorage.getItem(PERMISSIONS_KEY);
  return {
    token,
    decodedToken: decodedRaw ? (JSON.parse(decodedRaw) as Record<string, unknown>) : null,
    permissions: permissionsRaw ? (JSON.parse(permissionsRaw) as string[]) : [],
  };
}

export function setAuthTokenValuesInLocalStorage(data: {
  token: string;
  refreshToken?: string;
  decodedToken: Record<string, unknown>;
  permissions: string[];
}): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, data.token);
  localStorage.setItem(DECODED_TOKEN_KEY, JSON.stringify(data.decodedToken));
  localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(data.permissions));
  if (data.refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, data.refreshToken);
  }
}

export function removeAuthTokenValuesFromLocalStorage(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(DECODED_TOKEN_KEY);
  localStorage.removeItem(PERMISSIONS_KEY);
}

export function saveStoreSelection(selectedStore: Store | null, availableStores: Store[]): void {
  if (selectedStore) {
    localStorage.setItem(SELECTED_STORE_KEY, JSON.stringify(selectedStore));
  } else {
    localStorage.removeItem(SELECTED_STORE_KEY);
  }
  localStorage.setItem(AVAILABLE_STORES_KEY, JSON.stringify(availableStores));
}

export function loadStoreSelection(): StoredStoreData {
  const selected = localStorage.getItem(SELECTED_STORE_KEY);
  const available = localStorage.getItem(AVAILABLE_STORES_KEY);
  return {
    selectedStore: selected ? (JSON.parse(selected) as Store) : null,
    availableStores: available ? (JSON.parse(available) as Store[]) : [],
  };
}
