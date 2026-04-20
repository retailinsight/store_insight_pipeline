import { AuthUser } from "@shared/api";

const ANALYTICS_ROLE_KEY = "STORE_INSIGHT_ANALYTICS_ROLE_NAME";

declare global {
  interface Window {
    dataLayer: Array<Record<string, unknown>>;
    gtag?: (...args: unknown[]) => void;
  }
}

export function getEffectiveRoleName(user: Pick<AuthUser, "role"> & Partial<Pick<AuthUser, "roleName">>): string {
  const roleName = user.roleName?.trim();
  if (roleName) {
    return roleName;
  }

  const role = user.role?.trim();
  return role || "unknown";
}

function ensureDataLayer(): Array<Record<string, unknown>> {
  window.dataLayer = window.dataLayer || [];
  return window.dataLayer;
}

function setGaUserRole(roleName: string): void {
  if (typeof window.gtag !== "function") {
    return;
  }

  window.gtag("set", "user_properties", {
    role_name: roleName,
  });
}

function trackGaEvent(eventName: string, roleName: string): void {
  if (typeof window.gtag !== "function") {
    return;
  }

  window.gtag("event", eventName, {
    role_name: roleName,
    user_role: roleName,
  });
}

export function persistRoleName(roleName: string): void {
  localStorage.setItem(ANALYTICS_ROLE_KEY, roleName);
}

export function loadPersistedRoleName(): string | null {
  const roleName = localStorage.getItem(ANALYTICS_ROLE_KEY);
  if (!roleName) {
    return null;
  }
  return roleName;
}

export function clearPersistedRoleName(): void {
  localStorage.removeItem(ANALYTICS_ROLE_KEY);
}

export function applyAnalyticsUserContext(
  roleName: string,
  options: { eventName?: string; includeGaEvent?: boolean } = {}
): void {
  const dataLayer = ensureDataLayer();

  if (options.eventName) {
    dataLayer.push({
      event: options.eventName,
      user_role: roleName,
    });
  } else {
    dataLayer.push({
      user_role: roleName,
    });
  }

  setGaUserRole(roleName);

  if (options.eventName && options.includeGaEvent) {
    trackGaEvent(options.eventName, roleName);
  }
}

export function clearAnalyticsUserContext(): void {
  const dataLayer = ensureDataLayer();
  dataLayer.push({
    event: "logout",
    user_role: null,
  });

  if (typeof window.gtag === "function") {
    window.gtag("set", "user_properties", {
      role_name: "signed_out",
    });
    window.gtag("event", "logout", {
      user_role: "signed_out",
    });
  }
}
