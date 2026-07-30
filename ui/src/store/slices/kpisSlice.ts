import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";
import { KpiData } from "@/models";
import { fetchKpis } from "@/services/kpiService";
import { getErrorMessage } from "@/utils/helpers/errorMessage";
import type { RootState } from "@/store";

export interface KpisState {
  data: KpiData[];
  isLoading: boolean;
  error: string | null;
}

const initialState: KpisState = {
  data: [],
  isLoading: false,
  error: null,
};

export const fetchKpisThunk = createAsyncThunk<
  KpiData[],
  void,
  { rejectValue: string; state: RootState }
>("kpis/fetch", async (_, { rejectWithValue, getState }) => {
  try {
    const storeId = getState().auth.selectedStore?.id;
    return await fetchKpis(storeId);
  } catch (error) {
    return rejectWithValue(getErrorMessage(error));
  }
});

const kpisSlice = createSlice({
  name: "kpis",
  initialState,
  reducers: {
    clearKpis(state) {
      state.data = [];
      state.error = null;
      state.isLoading = false;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchKpisThunk.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchKpisThunk.fulfilled, (state, action) => {
        state.isLoading = false;
        state.data = action.payload;
        state.error = null;
      })
      .addCase(fetchKpisThunk.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload ?? "Failed to load KPI data";
      });
  },
});

export const { clearKpis } = kpisSlice.actions;
export default kpisSlice.reducer;
