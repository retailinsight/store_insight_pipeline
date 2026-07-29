export interface SuccessData {
  id: string;
  title: string;
  triggerTypes: string[];
  type: string;
  value: string;
  trendDirection: "up" | "down";
  trend: string;
  impact: string;
}

export interface SuccessesResponse {
  data: SuccessData[];
  meta: {
    limit: number;
    offset: number;
    total: number;
  };
}
