const env = import.meta.env;

const AUTH_BASE = (env.VITE_AUTH_API_URL as string) || "http://localhost:3125";
const API_VERSION = (env.VITE_API_VERSION as string) || "/api/v1";

export interface OAuthConfig {
  authorizationEndpoint: string;
  tokenEndpoint: string;
  logoutEndpoint: string;
  clientId: string;
  redirectUri: string;
  scope: string;
}

export const OAUTH_CONFIG: OAuthConfig = {
  authorizationEndpoint: `${AUTH_BASE}${API_VERSION}/oauth/authorize`,
  tokenEndpoint: `${AUTH_BASE}${API_VERSION}/oauth/token`,
  logoutEndpoint: `${AUTH_BASE}${API_VERSION}/oauth/token/revoke`,
  clientId: "",
  redirectUri: `${window.location.origin}/auth/callback`,
  scope: "store_insight_app",
};
