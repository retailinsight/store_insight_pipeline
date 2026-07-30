import { useEffect, useRef } from "react";
import { setSessionExpiredHandler } from "@/utils/auth/sessionHandler";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  initAuth,
  sessionExpired as sessionExpiredAction,
  fetchStoresThunk,
} from "@/store/slices/authSlice";
import { clearKpis } from "@/store/slices/kpisSlice";
import { clearSuccesses } from "@/store/slices/successesSlice";
import { clearActions } from "@/store/slices/actionsSlice";
import { useToast } from "@/hooks/useToast";
import { initiateLogin } from "@/utils/auth/oauthFlow";

export function AuthInitializer({ children }: { children: React.ReactNode }) {
  const dispatch = useAppDispatch();
  const { toast } = useToast();
  const initialized = useRef(false);
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    dispatch(initAuth());
  }, [dispatch]);

  // Fetch the live stores list whenever the user is authenticated.
  useEffect(() => {
    if (!isAuthenticated) return;
    dispatch(fetchStoresThunk());
  }, [dispatch, isAuthenticated]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      dispatch(sessionExpiredAction());
      dispatch(clearKpis());
      dispatch(clearSuccesses());
      dispatch(clearActions());
      toast({
        title: "Session Expired",
        description: "Your session has expired. Please log back in.",
        variant: "destructive",
      });
      // Short delay so the toast is visible before the redirect.
      const redirectDelay =
        Number(import.meta.env.VITE_APP_TIME_REDIRECT_AFTER_LOGOUT) || 3000;
      setTimeout(() => initiateLogin("/"), redirectDelay);
    });
    return () => {
      setSessionExpiredHandler(() => {});
    };
  }, [dispatch, toast]);

  return <>{children}</>;
}
