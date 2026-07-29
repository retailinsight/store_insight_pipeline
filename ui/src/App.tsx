import "./global.css";

import { BrowserRouter } from "react-router-dom";
import { Provider as ReduxProvider } from "react-redux";
import { createRoot } from "react-dom/client";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthInitializer } from "@/store/AuthInitializer";
import { SmartActionsProvider } from "@/contexts/SmartActionsContext";
import { AppRoutes } from "@/routes";
import { store } from "./store";

const queryClient = new QueryClient();

const App = () => (
  <ReduxProvider store={store}>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AuthInitializer>
            <SmartActionsProvider>
              <AppRoutes />
            </SmartActionsProvider>
          </AuthInitializer>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ReduxProvider>
);

createRoot(document.getElementById("root")!).render(<App />);
