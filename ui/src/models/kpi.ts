export interface KpiTarget {
  value: string;
  trendDirection: "up" | "down";
  trend: string;
}

export interface KpiPreviousAverage {
  value: string;
  trendDirection: "up" | "down";
  trend: string;
}

export interface KpiPerformanceBreakdown {
  [key: string]: string | number;
}

export interface KpiTopDriver {
  driver: string;
  subcategory: string;
  when: string;
  trendDirection: "up" | "down";
  trend: string;
}

export interface KpiCategoryPerformance {
  category: string;
  performance: string;
  warning: boolean;
}

export interface KpiTimeOfDayPerformance {
  time_period: string;
  performance: string;
  rag_status: "green" | "amber" | "red";
}

export interface KpiTimeOfDayAnalysis {
  "day:"?: string;
  performance: KpiTimeOfDayPerformance[];
}

export interface KpiDetails {
  target?: KpiTarget;
  previousAverage?: KpiPreviousAverage;
  performanceBreakdown?: KpiPerformanceBreakdown;
  keyInsights?: string[];
  summary?: string;
  topDrivers?: KpiTopDriver[];
  categoryPerformance?: KpiCategoryPerformance[];
  timeOfDayAnalysis?: KpiTimeOfDayAnalysis[];
}

export interface KpiData {
  id: string;
  name: string;
  value: string;
  trendDirection: "up" | "down";
  trend: string;
  clusterAverage: string;
  details: KpiDetails;
}

export interface KpisResponse {
  data: KpiData[];
  meta: {
    limit: number;
    offset: number;
    total: number;
  };
}
