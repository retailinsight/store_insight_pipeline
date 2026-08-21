import apiInstance from "@/utils/instance/apiInstance";
import { KpiData } from "@/models";

/**
 * Normalises any of the nesting shapes the KPI endpoints can return:
 *   [...] | { data: [...] } | { data: { data: [...] } } | { data: { data: { data: [...] } } }
 */
function extractKpis(payload: unknown): KpiData[] {
  if (Array.isArray(payload)) return payload as KpiData[];

  if (payload && typeof payload === "object") {
    const l1 = payload as Record<string, unknown>;
    if (Array.isArray(l1.data)) return l1.data as KpiData[];

    if (l1.data && typeof l1.data === "object") {
      const l2 = l1.data as Record<string, unknown>;
      if (Array.isArray(l2.data)) return l2.data as KpiData[];

      if (l2.data && typeof l2.data === "object") {
        const l3 = l2.data as Record<string, unknown>;
        if (Array.isArray(l3.data)) return l3.data as KpiData[];
      }
    }
  }

  throw new Error("Invalid KPI response format");
}

export async function fetchKpis(storeId?: number): Promise<KpiData[]> {
  try {
    const { data } = await apiInstance.get<unknown>("/kpis", {
      params: storeId ? { storeId: storeId } : undefined,
    });
    return extractKpis(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    const isAllowlistRejection =
      message.includes("403") &&
      message.includes('Table "kpis" is not in the allowed list');

    if (!isAllowlistRejection) throw error;

    const { data } = await apiInstance.get<unknown>("/kpi", {
      params: storeId ? { storeId: storeId } : undefined,
    });
    return extractKpis(data);
  }
}
