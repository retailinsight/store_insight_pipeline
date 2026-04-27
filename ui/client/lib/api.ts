import {
  AuthResponse,
  KpisResponse,
  SuccessesResponse,
  ActionsResponse,
} from "@shared/api";

// Normalize and resolve the API base URL
// In development, use relative paths (proxied via Vite)
// In production, use an explicit base URL if provided, otherwise use the remote API
function normalizeApiBaseUrl(rawBaseUrl: string): string {
  const trimmed = rawBaseUrl.trim();

  if (!trimmed) {
    // Default to relative API paths in development (proxied via Vite to localhost:3001)
    // In production, this will use relative paths to the same origin
    return "/api";
  }

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    // In deployed environments, guard against accidentally building with
    // localhost API URLs from a checked-in .env file.
    if (
      typeof window !== "undefined" &&
      window.location.hostname !== "localhost" &&
      /localhost|127\.0\.0\.1/.test(trimmed)
    ) {
      return "https://storeinsight-production.up.railway.app";
    }
    return trimmed.replace(/\/+$/, "");
  }

  if (trimmed.startsWith("/")) {
    return trimmed.replace(/\/+$/, "");
  }

  // If protocol is omitted (e.g. "api.example.com"), default to HTTPS.
  return `https://${trimmed}`.replace(/\/+$/, "");
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL || "");

// Shared-secret key sent as the ``X-API-Key`` header. Set ``VITE_API_KEY`` in
// the frontend env to match ``STORE_INSIGHT_API_KEY`` on the backend.
const API_KEY = (import.meta.env.VITE_API_KEY || "").trim();

function buildApiUrl(endpoint: string): string {
  if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
    return endpoint;
  }

  const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  return `${API_BASE_URL}${normalizedEndpoint}`;
}

function apiKeyHeader(): Record<string, string> {
  return API_KEY ? { "X-API-Key": API_KEY } : {};
}

async function parseJsonResponse<T>(response: Response, endpoint: string): Promise<T> {
  const text = await response.text();

  if (!text.trim()) {
    throw new Error(
      `API returned an empty response for ${endpoint} (${response.status} ${response.statusText})`
    );
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    const preview = text.slice(0, 180).replace(/\s+/g, " ");
    throw new Error(
      `API returned non-JSON response for ${endpoint} (${response.status} ${response.statusText}): ${preview}`
    );
  }
}

console.log("[API] Base URL set to:", API_BASE_URL);

// Token storage keys
const ACCESS_TOKEN_KEY = "STORE_INSIGHT_ACCESS_TOKEN";
const REFRESH_TOKEN_KEY = "STORE_INSIGHT_REFRESH_TOKEN";

// User data storage keys
const USER_ID_KEY = "STORE_INSIGHT_USER_ID";
const USER_EMAIL_KEY = "STORE_INSIGHT_USER_EMAIL";

// Session expiration handler
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

function handleSessionExpired(): void {
  if (onSessionExpired) {
    onSessionExpired();
  }
}

// ===== Token Management =====
export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function hasTokens(): boolean {
  return !!getAccessToken();
}

// ===== User Data Management =====
export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}

export function getUserEmail(): string | null {
  return localStorage.getItem(USER_EMAIL_KEY);
}

export function setUserData(userId: string, email: string): void {
  localStorage.setItem(USER_ID_KEY, userId);
  localStorage.setItem(USER_EMAIL_KEY, email);
}

export function clearUserData(): void {
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem(USER_EMAIL_KEY);
}

// ===== Auth =====
/**
 * Login with dev credentials to get access and refresh tokens
 */
export async function login(
  username: string = "dev-user",
  password: string = "dev-user"
): Promise<AuthResponse> {
  const loginUrl = buildApiUrl("/auth/login");
  console.log("[API] Attempting login to:", loginUrl, "with username:", username);

  try {
    const response = await fetch(loginUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...apiKeyHeader(),
      },
      body: JSON.stringify({ username, password }),
    });

    console.log("[API] Login response status:", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error("[API] Login error response:", errorText);
      
      // Return user-friendly message for authentication failures
      if (response.status === 401 || response.status === 403) {
        throw new Error("Incorrect username or password. Please try again.");
      }
      
      throw new Error(
        `Login failed (${response.status}): ${response.statusText}. ${errorText}`
      );
    }

    const data = await parseJsonResponse<AuthResponse>(response, loginUrl);
    console.log("[API] Login successful, tokens stored");
    console.log("[API] User data:", { id: data.user.id, username: data.user.username, stores: data.user.stores });
    setTokens(data.accessToken, data.refreshToken);
    // Store user ID and email (username) in local storage
    setUserData(data.user.id, data.user.username);
    return data;
  } catch (error) {
    console.error("[API] Login exception:", error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Login request failed: Network error or CORS issue");
  }
}

/**
 * Ensure we have valid tokens, logging in if necessary
 */
export async function ensureAuth(): Promise<AuthResponse | null> {
  if (hasTokens()) {
    return null; // Already authenticated
  }
  return login();
}

// ===== API Helpers =====
/**
 * Make an authenticated API request with bearer token
 */
async function authenticatedFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAccessToken();

  if (!token) {
    throw new Error("No authentication token available");
  }

  try {
    const response = await fetch(buildApiUrl(endpoint), {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...apiKeyHeader(),
        ...options.headers,
      },
    });

    // Handle 401 - token expired, need to re-auth
    if (response.status === 401) {
      clearTokens();
      handleSessionExpired();
      throw new Error("SESSION_EXPIRED");
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `API request failed (${response.status}): ${response.statusText}. ${errorText}`
      );
    }

    return parseJsonResponse<T>(response, buildApiUrl(endpoint));
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(
      "API request failed: Network error or CORS issue"
    );
  }
}

// ===== Data Fetching =====
/**
 * Fetch KPI data
 */
export async function fetchKpis(storeId?: number): Promise<KpisResponse> {
  const params = storeId != null ? `?store_id=${storeId}` : "";
  const primaryEndpoint = `/data/kpis${params}`;
  const fallbackEndpoint = `/data/kpi${params}`;

  console.log("[API] Fetching KPIs from:", buildApiUrl(primaryEndpoint));

  try {
    const result = await authenticatedFetch<KpisResponse>(primaryEndpoint);
    console.log("[API] KPIs fetched successfully:", result.data.length, "items");
    return result;
  } catch (error) {
    const message = getErrorMessage(error);
    const shouldFallback =
      message.includes("403") &&
      message.includes('Table "kpis" is not in the allowed list');

    if (!shouldFallback) {
      throw error;
    }

    console.warn(
      "[API] KPI endpoint rejected by backend allowlist. Retrying with:",
      buildApiUrl(fallbackEndpoint)
    );

    const fallbackResult = await authenticatedFetch<KpisResponse>(fallbackEndpoint);
    console.log(
      "[API] KPIs fetched successfully via fallback:",
      fallbackResult.data.length,
      "items"
    );
    return fallbackResult;
  }
}

/**
 * Fetch success data
 */
export async function fetchSuccesses(): Promise<SuccessesResponse> {
  console.log("[API] Fetching successes from:", buildApiUrl("/data/successes"));
  const result = await authenticatedFetch<SuccessesResponse>("/data/successes");
  console.log("[API] Successes fetched successfully:", result.data.length, "items");
  return result;
}

/**
 * Fetch action data
 */
export async function fetchActions(storeId?: number): Promise<ActionsResponse> {
  const params = storeId != null ? `?store_id=${storeId}` : "";
  const endpoint = `/data/actions${params}`;
  console.log("[API] Fetching actions from:", buildApiUrl(endpoint));
  const result = await authenticatedFetch<ActionsResponse>(endpoint);
  console.log("[API] Actions fetched successfully:", result.data.length, "items");
  return result;
}

/**
 * Complete an action with feedback
 */
export async function completeAction(
  actionId: number,
  opinion: "positive" | "negative",
  feedback: string = ""
): Promise<void> {
  console.log("[API] Completing action:", actionId, "with opinion:", opinion);
  await authenticatedFetch<{ message: string; data: unknown }>(
    `/actions/${actionId}/complete`,
    {
      method: "POST",
      body: JSON.stringify({ opinion, feedback }),
    }
  );
  console.log("[API] Action completed successfully");
}

/**
 * Submit user feedback
 */
export async function submitFeedback(
  feedback: string,
  storeId: number,
  userId: string
): Promise<void> {
  const timestamp = new Date().toISOString();
  console.log("[API] Submitting feedback for store:", storeId);
  await authenticatedFetch<{ message: string; data: unknown }>(
    `/feedback`,
    {
      method: "POST",
      body: JSON.stringify({ feedback, storeId, userId, timestamp }),
    }
  );
  console.log("[API] Feedback submitted successfully");
}

/**
 * Generic error handler for API errors
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred";
}
