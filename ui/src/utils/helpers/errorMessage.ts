import axios from "axios";

/**
 * Extracts a human-readable error message from any thrown value.
 * Special-cases axios errors so server-provided messages bubble up.
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { message?: string; error?: string }
      | string
      | undefined;

    if (typeof data === "string" && data.trim().length > 0) {
      return data;
    }
    if (data && typeof data === "object") {
      if (data.message) return data.message;
      if (data.error) return data.error;
    }

    if (error.response) {
      return `API request failed (${error.response.status}): ${error.response.statusText}`;
    }
    return error.message || "Network error or CORS issue";
  }

  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred";
}
