import apiInstance from "@/utils/instance/apiInstance";
import { Store } from "@/models";

/**
 * Normalises the nested response shapes the stores endpoint can return:
 *   [...] | { data: [...] } | { data: { data: [...] } }
 */
function extractStores(payload: unknown): Store[] {
  if (Array.isArray(payload)) return payload as Store[];

  if (payload && typeof payload === "object") {
    const l1 = payload as Record<string, unknown>;
    if (Array.isArray(l1.data)) return l1.data as Store[];

    if (l1.data && typeof l1.data === "object") {
      const l2 = l1.data as Record<string, unknown>;
      if (Array.isArray(l2.data)) return l2.data as Store[];
    }
  }

  throw new Error("Invalid stores response format");
}

export async function fetchStores(): Promise<Store[]> {
  const { data } = await apiInstance.get<unknown>("stores");
  return extractStores(data);
}
