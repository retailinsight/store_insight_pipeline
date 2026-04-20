/**
 * Shared code between client and server
 * Useful to share types between client and server
 * and/or small pure JS functions that can be used on both client and server
 */

/**
 * Example response type for /api/demo
 */
export interface DemoResponse {
  message: string;
}

// ===== Auth Types =====
export interface Store {
  id: number;
  name: string;
  location: string;
}

export interface AuthUser {
  id: string;
  username: string;
  role: string;
  roleName?: string;
  roleId: number;
  storeId: number;
  store?: Store;
  stores: Store[];
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

// ===== KPI Types =====
export interface KpiTarget {
  value: string;
  trend_direction: "up" | "down";
  trend: string;
}

export interface KpiPreviousAverage {
  value: string;
  trend_direction: "up" | "down";
  trend: string;
}

export interface KpiPerformanceBreakdown {
  [key: string]: string | number;
}

export interface KpiTopDriver {
  driver: string;
  Subcategory: string;
  When: string;
  trend_direction: "up" | "down";
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
  previous_average?: KpiPreviousAverage;
  performance_breakdown?: KpiPerformanceBreakdown;
  Key_insights?: string[];
  summary?: string;
  top_drivers?: KpiTopDriver[];
  category_performance?: KpiCategoryPerformance[];
  time_of_day_analysis?: KpiTimeOfDayAnalysis[];
}

export interface KpiData {
  id: string;
  name: string;
  value: string;
  trend_direction: "up" | "down";
  trend: string;
  cluster_average: string;
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

// ===== Success Types =====
export interface SuccessData {
  id: string;
  title: string;
  trigger_types: string[];
  type: string;
  value: string;
  trend_direction: "up" | "down";
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

// ===== Action Types =====
export interface ActionData {
  RUN_DATE: string;
  ALERT_TYPE: string;
  STORE_ID: number;
  SECTION: string;
  TYPE: "Availability" | "Waste" | string;
  TRIGGER_TYPES: string[];
  ISSUE: string;
  EXPLANATION: string;
  COST_IF_NOT_FIXED: string;
  RECOMMENDED_ACTION: string;
  SORT_VALUE: number;
}

export interface ActionsResponse {
  data: ActionData[];
  meta: {
    limit: number;
    offset: number;
    total: number;
  };
}
