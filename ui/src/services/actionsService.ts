import apiInstance from "@/utils/instance/apiInstance";
import { ActionData } from "@/models";

/**
 * Normalises any nesting depth the smartactions endpoint may return:
 *   [...] | { data: [...] } | { data: { data: [...] } } | { data: { data: { data: [...] } } }
 */
function extractActions(payload: unknown): ActionData[] {
  if (Array.isArray(payload)) return payload as ActionData[];

  if (payload && typeof payload === "object") {
    const l1 = payload as Record<string, unknown>;
    if (Array.isArray(l1.data)) return l1.data as ActionData[];

    if (l1.data && typeof l1.data === "object") {
      const l2 = l1.data as Record<string, unknown>;
      if (Array.isArray(l2.data)) return l2.data as ActionData[];

      if (l2.data && typeof l2.data === "object") {
        const l3 = l2.data as Record<string, unknown>;
        if (Array.isArray(l3.data)) return l3.data as ActionData[];
      }
    }
  }

  throw new Error("Invalid actions response format");
}

export async function fetchActions(storeId?: number): Promise<ActionData[]> {
  const { data } = await apiInstance.get<unknown>("smartactions", {
    params: storeId ? { storeId: storeId } : undefined,
  });
  return extractActions(data);
}
