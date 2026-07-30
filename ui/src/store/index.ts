import { configureStore } from "@reduxjs/toolkit";
import authReducer from "./slices/authSlice";
import kpisReducer from "./slices/kpisSlice";
import successesReducer from "./slices/successesSlice";
import actionsReducer from "./slices/actionsSlice";

export const store = configureStore({
  reducer: {
    auth: authReducer,
    kpis: kpisReducer,
    successes: successesReducer,
    actions: actionsReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
