import { ReactNode, useCallback, useEffect, useMemo, useRef } from "react";
import { SmartAction } from "@/components/SmartActionCard";
import { ActionStatus } from "@/components/SmartActionBoardCard";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  fetchActionsThunk,
  updateActionStatus as updateActionStatusAction,
  removeActionState,
} from "@/store/slices/actionsSlice";

import { useToast } from "@/hooks/useToast";

interface ActionState {
  id: number;
  status: ActionStatus;
  reminderDate?: Date;
}

interface SmartActionsContextType {
  actions: SmartAction[];
  actionStates: Map<number, ActionState>;
  isLoading: boolean;
  error: string | null;
  updateActionStatus: (
    id: number,
    status: ActionStatus,
    reminderDate?: Date,
  ) => void;
  removeAction: (id: number) => void;
  getActionStatus: (id: number) => ActionStatus;
  getVisibleActions: () => SmartAction[];
  getActionsByStatus: (status: ActionStatus) => SmartAction[];
}

/**
 * Mounts once at the root to drive the actions fetch lifecycle in response to
 * auth changes. Toast side effects live here (outside redux).
 */
export function SmartActionsProvider({ children }: { children: ReactNode }) {
  const dispatch = useAppDispatch();
  const { toast } = useToast();
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated);
  const authLoading = useAppSelector((s) => s.auth.isLoading);
  const selectedstoreId = useAppSelector((s) => s.auth.selectedStore?.id);
  const lastError = useRef<string | null>(null);
  const error = useAppSelector((s) => s.actions.error);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !selectedstoreId) return;
    dispatch(fetchActionsThunk());
  }, [dispatch, isAuthenticated, authLoading, selectedstoreId]);

  // Surface fetch errors via toast (skip session-expired which is handled globally).
  useEffect(() => {
    if (error && error !== lastError.current && error !== "SESSION_EXPIRED") {
      lastError.current = error;
      toast({
        title: "Failed to load actions",
        description: error,
        variant: "destructive",
      });
    }
    if (!error) {
      lastError.current = null;
    }
  }, [error, toast]);

  return <>{children}</>;
}

export function useSmartActions(): SmartActionsContextType {
  const dispatch = useAppDispatch();
  const actions = useAppSelector((s) => s.actions.data);
  const isLoading = useAppSelector((s) => s.actions.isLoading);
  const error = useAppSelector((s) => s.actions.error);
  const statesRecord = useAppSelector((s) => s.actions.states);

  // Reconstruct Map<number, ActionState> with Date objects for backward compat.
  const actionStates = useMemo(() => {
    const map = new Map<number, ActionState>();
    for (const id in statesRecord) {
      const entry = statesRecord[id];
      map.set(Number(id), {
        id: entry.id,
        status: entry.status,
        reminderDate: entry.reminderDate
          ? new Date(entry.reminderDate)
          : undefined,
      });
    }
    return map;
  }, [statesRecord]);

  const updateActionStatus = useCallback(
    (id: number, status: ActionStatus, reminderDate?: Date) => {
      dispatch(
        updateActionStatusAction({
          id,
          status,
          reminderDate: reminderDate?.toISOString(),
        }),
      );
    },
    [dispatch],
  );

  const removeAction = useCallback(
    (id: number) => {
      dispatch(removeActionState(id));
    },
    [dispatch],
  );

  const getActionStatus = useCallback(
    (id: number): ActionStatus => actionStates.get(id)?.status || "pending",
    [actionStates],
  );

  const getVisibleActions = useCallback(
    (): SmartAction[] =>
      actions.filter((action) => {
        const status = getActionStatus(action.id);
        return status === "pending" || status === "reminder_set";
      }),
    [actions, getActionStatus],
  );

  const getActionsByStatus = useCallback(
    (status: ActionStatus): SmartAction[] =>
      actions.filter((action) => getActionStatus(action.id) === status),
    [actions, getActionStatus],
  );

  return {
    actions,
    actionStates,
    isLoading,
    error,
    updateActionStatus,
    removeAction,
    getActionStatus,
    getVisibleActions,
    getActionsByStatus,
  };
}
