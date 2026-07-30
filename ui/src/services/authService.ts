import { OAUTH_CONFIG } from "@/utils/auth/oauthConfig";

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
  scope?: string;
}

export async function postToken(code: string): Promise<TokenResponse> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: OAUTH_CONFIG.redirectUri,
  });

  if (OAUTH_CONFIG.clientId) {
    body.append("client_id", OAUTH_CONFIG.clientId);
  }

  const response = await fetch(OAUTH_CONFIG.tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  if (!response.ok) {
    const message = await response.text().catch(() => response.statusText);
    throw new Error(`Token exchange failed (${response.status}): ${message}`);
  }

  return response.json() as Promise<TokenResponse>;
}
