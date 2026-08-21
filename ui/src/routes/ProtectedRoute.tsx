import { ReactNode, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAppSelector } from "@/store/hooks";
import { initiateLogin } from "@/utils/auth/oauthFlow";

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated);
  const isLoading = useAppSelector((s) => s.auth.isLoading);
  const location = useLocation();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      initiateLogin(location.pathname + location.search);
    }
  }, [isLoading, isAuthenticated, location.pathname, location.search]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-app-bg">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-4 border-brand-primary border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="font-dm-sans text-gray-600">
            {isLoading ? "Loading…" : "Redirecting to sign-in…"}
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
