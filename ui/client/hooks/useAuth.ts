import {
  useState,
  useEffect,
  useCallback,
  createContext,
  useContext,
  ReactNode,
  createElement,
} from "react";
import { useNavigate } from "react-router-dom";
import { AuthUser, Store } from "@shared/api";
import {
  login,
  hasTokens,
  clearTokens,
  getErrorMessage,
  setSessionExpiredHandler,
} from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

// Storage keys for persistence
const SELECTED_STORE_KEY = "STORE_INSIGHT_SELECTED_STORE";
const AVAILABLE_STORES_KEY = "STORE_INSIGHT_AVAILABLE_STORES";

function saveStoreData(selectedStore: Store | null, availableStores: Store[]): void {
  if (selectedStore) {
    localStorage.setItem(SELECTED_STORE_KEY, JSON.stringify(selectedStore));
  } else {
    localStorage.removeItem(SELECTED_STORE_KEY);
  }
  localStorage.setItem(AVAILABLE_STORES_KEY, JSON.stringify(availableStores));
}

function loadStoreData(): { selectedStore: Store | null; availableStores: Store[] } {
  const selectedStoreJson = localStorage.getItem(SELECTED_STORE_KEY);
  const availableStoresJson = localStorage.getItem(AVAILABLE_STORES_KEY);
  return {
    selectedStore: selectedStoreJson ? JSON.parse(selectedStoreJson) : null,
    availableStores: availableStoresJson ? JSON.parse(availableStoresJson) : [],
  };
}

interface UseAuthReturn {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AuthUser | null;
  error: string | null;
  selectedStore: Store | null;
  availableStores: Store[];
  canSwitchStores: boolean;
  login: (username?: string, password?: string) => Promise<void>;
  logout: (showSuccessMessage?: boolean) => void;
  ensureAuthenticated: () => Promise<void>;
  selectStore: (store: Store) => void;
}

const AuthContext = createContext<UseAuthReturn | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(hasTokens());
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);
  const [availableStores, setAvailableStores] = useState<Store[]>([]);
  const { toast } = useToast();
  const navigate = useNavigate();

  // Debug: Log store state changes
  useEffect(() => {
    console.log("[useAuth] selectedStore state changed to:", selectedStore);
  }, [selectedStore]);

  // Initialize auth on mount
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      try {
        // Only restore if we have tokens from a previous session
        if (hasTokens()) {
          console.log("[useAuth] Has existing tokens, restoring store data");
          const { selectedStore, availableStores } = loadStoreData();
          console.log("[useAuth] Restored from localStorage:", { selectedStore, availableStores });
          setSelectedStore(selectedStore);
          setAvailableStores(availableStores);
          setIsAuthenticated(true);
        } else {
          // No tokens - just mark as not authenticated, don't auto-login
          console.log("[useAuth] No tokens found, waiting for user login");
          setIsAuthenticated(false);
        }
      } catch (err) {
        const message = getErrorMessage(err);
        setError(message);
        setIsAuthenticated(false);
        toast({
          title: "Authentication Failed",
          description: message,
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, [toast]);

  // Set up session expiration handler
  useEffect(() => {
    const handleSessionExpiration = () => {
      console.log("[useAuth] Session expired, logging out and redirecting");
      clearTokens();
      saveStoreData(null, []);
      setIsAuthenticated(false);
      setUser(null);
      setSelectedStore(null);
      setAvailableStores([]);
      setError(null);
      
      toast({
        title: "Session Expired",
        description: "Your session has expired. Please log back in.",
        variant: "destructive",
      });
      
      // Redirect to login page
      navigate("/login", { replace: true });
    };

    setSessionExpiredHandler(handleSessionExpiration);

    // Cleanup
    return () => {
      setSessionExpiredHandler(() => {});
    };
  }, [toast, navigate]);

  const handleLogin = useCallback(
    async (username = "dev-user", password = "dev-user") => {
      console.log("[useAuth] handleLogin called with:", { username, password });
      setIsLoading(true);
      setError(null);
      try {
        const response = await login(username, password);
        console.log("[useAuth] Login response user:", response.user);
        setUser(response.user);
        // Use stores array from response
        const storesArray = response.user.stores || [];
        console.log("[useAuth] Extracted storesArray:", storesArray);
        if (storesArray.length > 0) {
          const selectedStore = storesArray[0];
          console.log("[useAuth] Setting selectedStore to:", selectedStore);
          setSelectedStore(selectedStore);
          setAvailableStores(storesArray);
          // Persist store data to localStorage
          saveStoreData(selectedStore, storesArray);
          setIsAuthenticated(true);
          setError(null);
        } else {
          throw new Error("Login successful but user has no stores assigned");
        }
        toast({
          title: "Login Successful",
          description: `Welcome, ${response.user.username}!`,
        });
      } catch (err) {
        const message = getErrorMessage(err);
        setError(message);
        setIsAuthenticated(false);
        toast({
          title: "Login Failed",
          description: message,
          variant: "destructive",
        });
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [toast]
  );

  const handleLogout = useCallback((showSuccessMessage: boolean = true) => {
    clearTokens();
    saveStoreData(null, []); // Clear stored store data
    setIsAuthenticated(false);
    setUser(null);
    setSelectedStore(null);
    setAvailableStores([]);
    setError(null);

    if (showSuccessMessage) {
      toast({
        title: "Successfully logged out",
        description: "See you next time!",
      });
    }
  }, [toast]);

  const ensureAuthenticated = useCallback(async () => {
    if (!isAuthenticated) {
      throw new Error("Not authenticated");
    }
  }, [isAuthenticated]);

  const handleSelectStore = useCallback((store: Store) => {
    console.log("[useAuth] Selecting store:", store);
    setSelectedStore(store);
    // Save the selected store to localStorage
    saveStoreData(store, availableStores);
  }, [availableStores]);

  const canSwitchStores = user?.roleId === 2;

  const value: UseAuthReturn = {
    isAuthenticated,
    isLoading,
    user,
    error,
    selectedStore,
    availableStores,
    canSwitchStores,
    login: handleLogin,
    logout: handleLogout,
    ensureAuthenticated,
    selectStore: handleSelectStore,
  };

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): UseAuthReturn {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
