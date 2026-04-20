import {
  createContext,
  useContext,
  useState,
  ReactNode,
  useEffect,
  useCallback,
} from "react";
import { SmartAction } from "@/components/SmartActionCard";
import { ActionStatus } from "@/components/SmartActionBoardCard";
import { ActionData } from "@shared/api";
import { fetchActions, getErrorMessage } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";

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
  updateActionStatus: (id: number, status: ActionStatus, reminderDate?: Date) => void;
  removeAction: (id: number) => void;
  getActionStatus: (id: number) => ActionStatus;
  getVisibleActions: () => SmartAction[];
  getActionsByStatus: (status: ActionStatus) => SmartAction[];
}

const SmartActionsContext = createContext<SmartActionsContextType | undefined>(
  undefined
);

function generateBullets(explanation: string): string[] {
  // Split explanation into sentences
  const sentences = explanation
    .split(/(?<=[.!?])\s+/)
    .filter((s) => s.trim().length > 0);

  // Return first 3-4 sentences as bullets, or all if fewer
  return sentences.slice(0, 4);
}

function transformActions(actions: ActionData[]): SmartAction[] {
  return actions.map((action, index) => ({
    id: index + 1,
    title: action.ISSUE,
    description: action.EXPLANATION,
    bullets: generateBullets(action.EXPLANATION),
    warning: action.COST_IF_NOT_FIXED,
    badges: {
      section: action.SECTION,
      type: action.TYPE,
    },
    recommendedAction: action.RECOMMENDED_ACTION,
  }));
}

export function SmartActionsProvider({ children }: { children: ReactNode }) {
  const [actions, setActions] = useState<SmartAction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // State is stored in memory only - resets on browser refresh
  // but persists when navigating between pages during the same session
  const [actionStates, setActionStates] = useState<Map<number, ActionState>>(
    new Map()
  );

  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { toast } = useToast();

  // Fetch actions on mount or when authenticated
  useEffect(() => {
    const loadActions = async () => {
      if (authLoading) {
        setIsLoading(true);
        return;
      }

      // Clear stale data if user is not authenticated.
      if (!isAuthenticated) {
        setActions([]);
        setError(null);
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        const response = await fetchActions();
        const transformedActions = transformActions(response.data);
        setActions(transformedActions);
        setError(null);
      } catch (err) {
        const message = getErrorMessage(err);
        
        // Don't show error for session expiration - the session handler will show its own message
        if (message !== "SESSION_EXPIRED") {
          setError(message);
          toast({
            title: "Failed to load actions",
            description: message,
            variant: "destructive",
          });
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadActions();
  }, [isAuthenticated, authLoading, toast]);

  const updateActionStatus = useCallback(
    (id: number, status: ActionStatus, reminderDate?: Date) => {
      setActionStates((prev) => {
        const newMap = new Map(prev);
        newMap.set(id, { id, status, reminderDate });
        return newMap;
      });
    },
    []
  );

  const removeAction = useCallback((id: number) => {
    setActionStates((prev) => {
      const newMap = new Map(prev);
      newMap.delete(id);
      return newMap;
    });
  }, []);

  const getActionStatus = useCallback(
    (id: number): ActionStatus => {
      return actionStates.get(id)?.status || "pending";
    },
    [actionStates]
  );

  const getVisibleActions = useCallback((): SmartAction[] => {
    return actions.filter((action) => {
      const status = getActionStatus(action.id);
      return status === "pending" || status === "reminder_set";
    });
  }, [actions, getActionStatus]);

  const getActionsByStatus = useCallback(
    (status: ActionStatus): SmartAction[] => {
      return actions.filter((action) => getActionStatus(action.id) === status);
    },
    [actions, getActionStatus]
  );

  return (
    <SmartActionsContext.Provider
      value={{
        actions,
        actionStates,
        isLoading,
        error,
        updateActionStatus,
        removeAction,
        getActionStatus,
        getVisibleActions,
        getActionsByStatus,
      }}
    >
      {children}
    </SmartActionsContext.Provider>
  );
}

export function useSmartActions() {
  const context = useContext(SmartActionsContext);
  if (context === undefined) {
    throw new Error("useSmartActions must be used within a SmartActionsProvider");
  }
  return context;
}
