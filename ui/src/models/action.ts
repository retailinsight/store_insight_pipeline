export interface ActionData {
  runDate: string;
  alertType: string;
  storeId: number;
  section: string;
  type: string;
  triggerTypes: string[];
  issue: string;
  explanation: string;
  costIfNotFixed: string;
  recommendedAction: string;
  sortValue: number;
}

export interface ActionsResponse {
  data: ActionData[];
  meta: {
    limit: number;
    offset: number;
    total: number;
  };
}
