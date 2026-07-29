import { useRoutes, type RouteObject } from "react-router-dom";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import Index from "@/pages/Index";
import SmartActionsPage from "@/pages/SmartActionsPage";
import SuccessesPage from "@/pages/SuccessesPage";
import NotFound from "@/pages/NotFound";

const routes: RouteObject[] = [
  // Public routes
  { path: "/login", element: <Login /> },
  { path: "/auth/callback", element: <AuthCallback /> },

  // Protected routes
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <Index />
      </ProtectedRoute>
    ),
  },
  {
    path: "/smart-actions",
    element: (
      <ProtectedRoute>
        <SmartActionsPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "/successes",
    element: (
      <ProtectedRoute>
        <SuccessesPage />
      </ProtectedRoute>
    ),
  },

  { path: "*", element: <NotFound /> },
];

export function AppRoutes() {
  return useRoutes(routes);
}
