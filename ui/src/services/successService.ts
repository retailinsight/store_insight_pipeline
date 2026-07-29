import apiInstance from "@/utils/instance/apiInstance";
import { SuccessesResponse } from "@/models";

export async function fetchSuccesses(): Promise<SuccessesResponse> {
  const { data } = await apiInstance.get<{ data: SuccessesResponse }>("kpis/successes");
  return data.data;
}
