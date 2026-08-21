let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

export function handleSessionExpired(): void {
  if (onSessionExpired) {
    onSessionExpired();
  }
}
