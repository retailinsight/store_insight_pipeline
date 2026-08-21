import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";
import { ActionData } from "@/models";
import { fetchActions } from "@/services/actionsService";
import { getErrorMessage } from "@/utils/helpers/errorMessage";
import type { SmartAction } from "@/components/SmartActionCard";
import type { ActionStatus } from "@/components/SmartActionBoardCard";
import type { RootState } from "@/store";

export interface ActionState {
  id: number;
  status: ActionStatus;
  reminderDate?: string;
}

export interface ActionsState {
  data: SmartAction[];
  isLoading: boolean;
  error: string | null;
  states: Record<number, ActionState>;
}

const initialState: ActionsState = {
  data: [],
  isLoading: false,
  error: null,
  states: {},
};

// ===== Transform helpers =====
function generateBullets(explanation: string): string[] {
  const sentences = explanation
    .split(/(?<=[.!?])\s+/)
    .filter((s) => s.trim().length > 0);
  return sentences.slice(0, 4);
}

function transformActions(actions: ActionData[]): SmartAction[] {
  return actions.map((action, index) => ({
    id: index + 1,
    title: action.issue,
    description: action.explanation,
    bullets: generateBullets(action.explanation),
    warning: action.costIfNotFixed,
    badges: {
      section: action.section,
      type: action.type,
    },
    recommendedAction: action.recommendedAction,
  }));
}

// ===== Thunk =====
export const fetchActionsThunk = createAsyncThunk<
  SmartAction[],
  void,
  { rejectValue: string; state: RootState }
>("actions/fetch", async (_, { rejectWithValue, getState }) => {
  try {
    const storeId = getState().auth.selectedStore?.id;
    return transformActions(await fetchActions(storeId));
  } catch (error) {
    return rejectWithValue(getErrorMessage(error));
  }
});

// ===== Slice =====
const actionsSlice = createSlice({
  name: "actions",
  initialState,
  reducers: {
    updateActionStatus(
      state,
      action: PayloadAction<{
        id: number;
        status: ActionStatus;
        reminderDate?: string;
      }>,
    ) {
      const { id, status, reminderDate } = action.payload;
      state.states[id] = { id, status, reminderDate };
    },
    removeActionState(state, action: PayloadAction<number>) {
      delete state.states[action.payload];
    },
    clearActions(state) {
      state.data = [];
      state.states = {};
      state.error = null;
      state.isLoading = false;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchActionsThunk.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchActionsThunk.fulfilled, (state, action) => {
        state.isLoading = false;
        state.data = action.payload;
        state.error = null;
      })
      .addCase(fetchActionsThunk.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload ?? "Failed to load actions";
      });
  },
});

export const { updateActionStatus, removeActionState, clearActions } =
  actionsSlice.actions;

export default actionsSlice.reducer;
