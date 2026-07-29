import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";
import { SuccessData } from "@/models";
import { fetchSuccesses } from "@/services/successService";
import { getErrorMessage } from "@/utils/helpers/errorMessage";

export interface SuccessesState {
  data: SuccessData[];
  isLoading: boolean;
  error: string | null;
}

const initialState: SuccessesState = {
  data: [],
  isLoading: false,
  error: null,
};

export const fetchSuccessesThunk = createAsyncThunk<
  SuccessData[],
  void,
  { rejectValue: string }
>("successes/fetch", async (_, { rejectWithValue }) => {
  try {
    const response = await fetchSuccesses();
    return response.data;
  } catch (error) {
    return rejectWithValue(getErrorMessage(error));
  }
});

const successesSlice = createSlice({
  name: "successes",
  initialState,
  reducers: {
    clearSuccesses(state) {
      state.data = [];
      state.error = null;
      state.isLoading = false;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchSuccessesThunk.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchSuccessesThunk.fulfilled, (state, action) => {
        state.isLoading = false;
        state.data = action.payload;
        state.error = null;
      })
      .addCase(fetchSuccessesThunk.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload ?? "Failed to load success data";
      });
  },
});

export const { clearSuccesses } = successesSlice.actions;
export default successesSlice.reducer;
