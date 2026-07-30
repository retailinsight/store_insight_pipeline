import { OAUTH_CONFIG } from "./oauthConfig";
import { removeAuthTokenValuesFromLocalStorage } from "./localStorageAuthHelper";
import { getAccessToken } from "./tokenStorage";

const SESSION_KEY_STATE = "oauth_state";
const SESSION_KEY_RETURN_TO = "oauth_return_to";

function generateState(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

export function initiateLogin(returnTo = "/"): void {
  const state = generateState();
  sessionStorage.setItem(SESSION_KEY_STATE, state);
  sessionStorage.setItem(SESSION_KEY_RETURN_TO, returnTo);

  const params = new URLSearchParams({
    redirect_uri: OAUTH_CONFIG.redirectUri,
    state,
    scope: OAUTH_CONFIG.scope,
    response_type: "code",
  });

  if (OAUTH_CONFIG.clientId) {
    params.append("client_id", OAUTH_CONFIG.clientId);
  }

  window.location.href = `${OAUTH_CONFIG.authorizationEndpoint}?${params.toString()}`;
}

export function initiateLogout(): void {
  const accessToken = getAccessToken();
  removeAuthTokenValuesFromLocalStorage();

  if (accessToken) {
    void fetch(OAUTH_CONFIG.logoutEndpoint, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    }).catch(() => undefined);
  }

  initiateLogin("/");
}

export function consumeReturnTo(): string {
  const path = sessionStorage.getItem(SESSION_KEY_RETURN_TO) ?? "/";
  sessionStorage.removeItem(SESSION_KEY_RETURN_TO);
  return path;
}

export function consumeState(): string | null {
  const state = sessionStorage.getItem(SESSION_KEY_STATE);
  sessionStorage.removeItem(SESSION_KEY_STATE);
  return state;
}

