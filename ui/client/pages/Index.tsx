import { useState, useEffect } from "react";
import { MessageCircle } from "lucide-react";
import Layout from "@/components/Layout";
import KpiWidget from "@/components/KpiWidget";
import SuccessCard from "@/components/SuccessCard";
import SmartActionCard from "@/components/SmartActionCard";
import KpiDetailPanel from "@/components/KpiDetailPanel";
import FeedbackDialog from "@/components/dialogs/FeedbackDialog";
import { useSmartActions } from "@/contexts/SmartActionsContext";
import { fetchKpis, fetchSuccesses, getErrorMessage, submitFeedback, getUserId } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { KpiData, SuccessData } from "@shared/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ── Data transformation helpers ──────────────────────────────────────────────

function transformKpiData(kpis: KpiData[]): Array<{
  type: "overall" | "availability" | "waste";
  label: string;
  value: string;
  change: string;
  changeLabel: string;
  trend: "up" | "down";
  clusterAvg: string;
  icon?: "availability" | "waste";
}> {
  return kpis.map((kpi) => {
    let type: "overall" | "availability" | "waste" = "overall";
    let icon: "availability" | "waste" | undefined;

    if (kpi.name.toLowerCase().includes("availability")) {
      type = "availability";
      icon = "availability";
    } else if (kpi.name.toLowerCase().includes("waste")) {
      type = "waste";
      icon = "waste";
    }

    return {
      type,
      label: kpi.name,
      value: kpi.value,
      change: kpi.trend.startsWith("+") ? kpi.trend : "+" + kpi.trend,
      changeLabel: "",
      trend: kpi.trend_direction,
      clusterAvg: kpi.cluster_average,
      icon,
    };
  });
}


// ── Medal SVG ────────────────────────────────────────────────────────────────

function MedalIcon() {
  return (
    <svg width="20" height="23" viewBox="0 0 21 24" fill="none">
      <path d="M20.6971 0.938961C20.3321 0.350985 19.7001 0 19.0082 0H15.9993C14.4653 0 13.0904 0.853964 12.4124 2.22991L10.5515 6.00275C10.5305 6.00275 10.5095 5.99975 10.4885 5.99975C10.4745 5.99975 10.4615 6.00175 10.4475 6.00175L8.58659 2.22991C7.90762 0.853964 6.53368 0 4.99974 0H1.99087C1.29889 0 0.666921 0.350985 0.300936 0.938961C-0.0640485 1.52694 -0.0990471 2.24891 0.20694 2.86988L3.43881 9.42261C2.22186 10.9575 1.48889 12.8935 1.48889 15.0004C1.48889 19.9622 5.52672 24 10.4885 24C15.4503 24 19.4881 19.9622 19.4881 15.0004C19.4881 12.9015 18.7602 10.9735 17.5512 9.44061L20.7921 2.87088C21.0991 2.24991 21.0631 1.52794 20.6981 0.939961L20.6971 0.938961ZM4.99874 1.99992C5.76571 1.99992 6.45268 2.4269 6.79167 3.11487L8.3466 6.26774C7.08265 6.57773 5.9227 7.1517 4.93074 7.93367L1.98987 1.99992H4.99874ZM10.4875 21.9991C6.62767 21.9991 3.4878 18.8592 3.4878 14.9994C3.4878 11.3395 6.31269 8.33165 9.89654 8.02967C9.89754 8.02967 9.89854 8.02967 9.90054 8.02967C10.0945 8.01367 10.2905 7.99967 10.4885 7.99967C14.3484 7.99967 17.4882 11.1395 17.4882 14.9994C17.4882 18.8592 14.3484 21.9991 10.4885 21.9991H10.4875ZM16.0573 7.94467C15.0673 7.1607 13.9094 6.58573 12.6474 6.27274L14.2054 3.11487C14.5443 2.4269 15.2313 1.99992 15.9983 1.99992L18.9982 1.98492L16.0573 7.94467ZM14.6443 14.4094C14.6443 14.7704 14.3933 15.0744 14.1054 15.2344L12.6154 16.0623L13.2764 17.8653C13.4044 18.2142 13.2884 18.6062 12.9914 18.8302C12.6874 19.0592 12.2684 19.0562 11.9685 18.8232L10.4865 17.6773L9.00457 18.8232C8.70359 19.0552 8.2846 19.0582 7.98162 18.8302C7.68463 18.6062 7.56863 18.2152 7.69663 17.8653L8.3576 16.0623L6.86766 15.2344C6.57968 15.0744 6.32869 14.7704 6.32869 14.4094C6.32869 14.1034 6.59467 13.7654 7.02466 13.7654H9.16457L9.73154 11.5905C9.82154 11.2455 10.1305 11.0055 10.4865 10.9995C10.8415 11.0065 11.1515 11.2455 11.2415 11.5905L11.8085 13.7654H13.9484C14.3784 13.7654 14.6443 14.1024 14.6443 14.4094Z" fill="#577DF7"/>
    </svg>
  );
}

function LightningIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M12.5658 24H8.71882L10.7188 16H6.58582C6.18639 15.9998 5.79255 15.9062 5.43575 15.7267C5.07894 15.5472 4.76908 15.2867 4.53092 14.966C4.29276 14.6454 4.13291 14.2734 4.06413 13.88C3.99535 13.4865 4.01956 13.0824 4.13482 12.7L7.97582 0H17.4428L14.4428 8H18.4658C18.9235 8.00029 19.3726 8.1246 19.7653 8.35972C20.1581 8.59484 20.4797 8.93197 20.6962 9.33529C20.9126 9.73861 21.0157 10.193 20.9945 10.6503C20.9733 11.1075 20.8286 11.5504 20.5758 11.932L12.5658 24ZM11.2808 22H11.4928L18.9088 10.826C18.962 10.7459 18.9924 10.6528 18.9969 10.5568C19.0013 10.4607 18.9797 10.3653 18.9343 10.2806C18.8888 10.1958 18.8213 10.125 18.7388 10.0756C18.6563 10.0262 18.562 10.0001 18.4658 10H11.5568L14.5568 2H9.45982L6.04882 13.276C6.02336 13.3599 6.01789 13.4485 6.03286 13.5348C6.04784 13.6212 6.08283 13.7028 6.13503 13.7732C6.18724 13.8436 6.2552 13.9008 6.33348 13.9401C6.41177 13.9795 6.49819 14 6.58582 14H13.2858L11.2808 22Z" fill="#577DF7"/>
    </svg>
  );
}

// ── Format helpers ───────────────────────────────────────────────────────────

function formatDateTime(date: Date) {
  const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const day = dayNames[date.getDay()];
  const d = date.getDate();
  const month = monthNames[date.getMonth()];
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return { date: `${day}, ${d} ${month} ${year}`, time: `${hours}:${minutes}` };
}

function calculateTotalCost(actions: any[]): number {
  return actions.reduce((total, action) => {
    if (!action.warning) return total;
    // Extract the pound amount from warning text like "If this continues... £1234.56..."
    const match = action.warning.match(/£([\d,]+\.?\d*)/);
    if (match) {
      const value = parseFloat(match[1].replace(/,/g, ''));
      return total + value;
    }
    return total;
  }, 0);
}

function formatCurrency(amount: number): string {
  return '£' + amount.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Dashboard Page ───────────────────────────────────────────────────────────

export default function Index() {
  const {
    actions: allActions,
    getVisibleActions,
    updateActionStatus,
    getActionsByStatus,
    isLoading: actionsLoading,
  } = useSmartActions();

  const { isAuthenticated, ensureAuthenticated, selectedStore, availableStores, selectStore } = useAuth();
  const { toast } = useToast();

  const [kpisData, setKpisData] = useState<KpiData[]>([]);
  const [kpisLoading, setKpisLoading] = useState(true);
  const [kpisError, setKpisError] = useState<string | null>(null);

  const [successesData, setSuccessesData] = useState<SuccessData[]>([]);
  const [successesLoading, setSuccessesLoading] = useState(true);
  const [successesError, setSuccessesError] = useState<string | null>(null);

  const [now, setNow] = useState(new Date());
  const [selectedKpi, setSelectedKpi] = useState<KpiData | null>(null);
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);

  // Fetch KPI data
  useEffect(() => {
    const loadKpis = async () => {
      if (!isAuthenticated) {
        try {
          await ensureAuthenticated();
        } catch {
          setKpisError("Failed to authenticate");
          setKpisLoading(false);
          return;
        }
      }

      try {
        const response = await fetchKpis(selectedStore?.id);
        setKpisData(response.data);
        setKpisError(null);
      } catch (err) {
        const message = getErrorMessage(err);
        
        // Don't show error for session expiration - the session handler will show its own message
        if (message !== "SESSION_EXPIRED") {
          setKpisError(message);
          toast({
            title: "Failed to load KPI data",
            description: message,
            variant: "destructive",
          });
        }
      } finally {
        setKpisLoading(false);
      }
    };

    loadKpis();
  }, [isAuthenticated, ensureAuthenticated, selectedStore, toast]);

  // Fetch successes data
  useEffect(() => {
    const loadSuccesses = async () => {
      if (!isAuthenticated) {
        try {
          await ensureAuthenticated();
        } catch {
          setSuccessesError("Failed to authenticate");
          setSuccessesLoading(false);
          return;
        }
      }

      try {
        const response = await fetchSuccesses();
        setSuccessesData(response.data);
        setSuccessesError(null);
      } catch (err) {
        const message = getErrorMessage(err);
        
        // Don't show error for session expiration - the session handler will show its own message
        if (message !== "SESSION_EXPIRED") {
          setSuccessesError(message);
          toast({
            title: "Failed to load success data",
            description: message,
            variant: "destructive",
          });
        }
      } finally {
        setSuccessesLoading(false);
      }
    };

    loadSuccesses();
  }, [isAuthenticated, ensureAuthenticated, toast]);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const actions = getVisibleActions();
  const completedActions = getActionsByStatus("completed");
  const couldNotCompleteActions = getActionsByStatus("couldnt_complete");
  const completedCount = completedActions.length + couldNotCompleteActions.length;
  const totalActions = allActions.length;
  const progressPct = Math.round((completedCount / totalActions) * 100);

  const handleSubmitFeedback = async (feedback: string) => {
    try {
      // Get store from auth context and user ID from localStorage
      if (!selectedStore) {
        throw new Error("Store not available");
      }

      const userId = getUserId();
      if (!userId) {
        throw new Error("User not authenticated");
      }

      // Call API with required params
      await submitFeedback(feedback, selectedStore.id, userId);

      // Close dialog on success
      setFeedbackDialogOpen(false);

      // Show success toast
      toast({
        title: "Thank you!",
        description: "Your feedback has been received and will help us improve.",
      });
    } catch (error) {
      // Extract error message
      const errorMessage = error instanceof Error ? error.message : "Failed to submit feedback";

      // Show error toast
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  return (
    <Layout>
      {/* Page header — on mobile add left padding to clear the hamburger button */}
      <div className="px-5 md:px-8 pt-6 pb-4 pl-16 md:pl-8 shrink-0 flex flex-col gap-1 animate-panel-in opacity-0" style={{ animationDelay: '100ms' }}>
        <div className="flex items-center justify-between gap-4">
          <h1 className="font-bebas text-[32px] text-black dark:text-white tracking-wide">
            Store {selectedStore?.id}: {selectedStore?.name}
          </h1>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setFeedbackDialogOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors md:px-4"
              title="Send us your feedback"
            >
              <MessageCircle size={18} />
              <span className="hidden md:inline">Send feedback</span>
            </button>
            {availableStores.length > 1 && (
              <div className="flex items-center gap-2">
                <span className="font-dm-sans text-sm text-gray-600 dark:text-white/60">
                  Switch store:
                </span>
                <Select
                  value={String(selectedStore?.id || "")}
                  onValueChange={(storeId) => {
                    const selected = availableStores.find(s => String(s.id) === storeId);
                    if (selected) {
                      selectStore(selected);
                    }
                  }}
                >
                  <SelectTrigger className="w-[250px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {availableStores.map((store) => (
                      <SelectItem key={store.id} value={String(store.id)}>
                        Store {store.id}: {store.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 text-black/50 dark:text-white/50">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
            <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674ZM12.3343 12.0001C12.3343 11.4475 12.7816 11.0002 13.3342 11.0002C13.8859 11.0002 14.3341 11.4475 14.3341 12.0001C14.3341 12.5518 13.8859 13 13.3342 13C12.7816 13 12.3343 12.5518 12.3343 12.0001ZM9.00051 12.0001C9.00051 11.4475 9.44783 11.0002 10.0005 11.0002C10.5531 11.0002 11.0004 11.4475 11.0004 12.0001C11.0004 12.5518 10.5531 13 10.0005 13C9.44783 13 9.00051 12.5518 9.00051 12.0001ZM5.66676 12.0001C5.66676 11.4475 6.11498 11.0002 6.6667 11.0002C7.21933 11.0002 7.66665 11.4475 7.66665 12.0001C7.66665 12.5518 7.21933 13 6.6667 13C6.11498 13 5.66676 12.5518 5.66676 12.0001Z" fill="currentColor"/>
          </svg>
          <span className="font-dm-sans text-sm">
            {formatDateTime(now).date} &bull; {formatDateTime(now).time}
          </span>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 flex flex-col gap-8 md:gap-10 min-h-0">

        {/* ── KPI row: horizontal on md+, stacked on mobile ── */}
        <div className="flex flex-col md:flex-row items-stretch gap-4 md:gap-6">
          {kpisLoading ? (
            // Loading skeleton
            <>
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="flex-1 h-48 rounded-2xl bg-white dark:bg-white/5 animate-pulse"
                />
              ))}
            </>
          ) : kpisError ? (
            <div className="w-full p-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300">
              Failed to load KPI data: {kpisError}
            </div>
          ) : (
            kpisData.map((kpi, i) => {
              const transformedKpi = transformKpiData([kpi])[0];
              return (
                <KpiWidget
                  key={transformedKpi.label}
                  {...transformedKpi}
                  animationDelay={i * 150}
                  onClick={() => setSelectedKpi(kpi)}
                />
              );
            })
          )}
        </div>

        {/* ── Recent Team Successes ── */}
        <section className="flex flex-col gap-6 rounded-2xl bg-white dark:bg-white/5 pt-4 px-6 pb-4 shadow-[1px_1px_16px_0_rgba(0,0,0,0.08)] animate-panel-in opacity-0" style={{ animationDelay: '500ms' }}>
          {/* Header */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-brand-primary-100 shrink-0">
              <MedalIcon />
            </div>
            <h2 className="font-bebas text-3xl text-black/50 dark:text-white/50 tracking-wide">
              Recent Team Successes
            </h2>
          </div>

          {/* Success cards: row on md+, stacked on mobile */}
          {successesLoading ? (
            <div className="flex flex-col gap-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-32 rounded-lg bg-white dark:bg-white/5 animate-pulse"
                />
              ))}
            </div>
          ) : successesError ? (
            <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300">
              Failed to load success data: {successesError}
            </div>
          ) : successesData.length === 0 ? (
            <div className="p-8 text-center text-gray-500 dark:text-white/60">
              No recent successes to display
            </div>
          ) : (
            <div className="flex flex-col md:flex-row items-stretch rounded-2xl overflow-hidden">
              {successesData.map((s, i) => (
                <SuccessCard
                  key={s.id}
                  title={s.title}
                  trigger_types={s.trigger_types}
                  type={s.type}
                  value={s.value}
                  trend_direction={s.trend_direction}
                  trend={s.trend}
                  impact={s.impact}
                  isFirst={i === 0}
                  isLast={i === successesData.length - 1}
                />
              ))}
            </div>
          )}
        </section>

        {/* ── Smart Actions ── */}
        <section className="flex flex-col gap-6 rounded-2xl bg-white/20 dark:bg-white/5 p-6 shadow-[1px_1px_16px_0_rgba(0,0,0,0.08)] animate-panel-in opacity-0" style={{ animationDelay: '700ms' }} data-testid="section-next-best-actions">
          {/* Header */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-brand-primary-100">
              <LightningIcon />
            </div>
            <h2 className="font-bebas text-3xl text-black/50 dark:text-white/50 tracking-wide">
              Today's Next Best Actions
            </h2>
            <span className="flex items-center px-4 py-1 rounded-full bg-app-lime font-dm-sans text-sm text-black" data-testid="nba-priority-badge">
              {actions.length} priority action{actions.length !== 1 ? "s" : ""} worth {formatCurrency(calculateTotalCost(allActions))}
            </span>
          </div>

          {/* Progress bar */}
          {completedCount > 0 && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="font-dm-sans text-xs text-gray-600 dark:text-white/60">
                  {completedCount} of {totalActions} actions completed today
                </span>
                <span className="font-dm-sans text-xs font-semibold text-brand-primary">
                  {progressPct}%
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-brand-primary-200 overflow-hidden">
                <div
                  className="h-full rounded-full bg-brand-primary transition-all duration-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          )}

          {/* Action cards */}
          {actionsLoading ? (
            <div className="flex flex-col gap-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-48 rounded-lg bg-white dark:bg-white/5 animate-pulse"
                />
              ))}
            </div>
          ) : actions.length > 0 ? (
            <div className="flex flex-col gap-4">
              {actions.map((action, i) => (
                <SmartActionCard
                  key={action.id}
                  action={action}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4 py-12 text-center">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-app-lime">
                <svg width="32" height="32" viewBox="0 0 20 20" fill="none">
                  <path d="M16.8609 4.19619L7.64819 13.4082C7.58625 13.4704 7.51264 13.5197 7.43159 13.5534C7.35053 13.5871 7.26363 13.6044 7.17586 13.6044C7.08809 13.6044 7.00118 13.5871 6.92013 13.5534C6.83908 13.5197 6.76547 13.4704 6.70353 13.4082L3.14086 9.84219C3.07892 9.78001 3.00531 9.73067 2.92426 9.697C2.8432 9.66333 2.7563 9.646 2.66853 9.646C2.58076 9.646 2.49385 9.66333 2.4128 9.697C2.33174 9.73067 2.25813 9.78001 2.19619 9.84219C2.13401 9.90413 2.08467 9.97774 2.051 10.0588C2.01733 10.1399 2 10.2268 2 10.3145C2 10.4023 2.01733 10.4892 2.051 10.5703C2.08467 10.6513 2.13401 10.7249 2.19619 10.7869L5.76019 14.3502C6.13616 14.7255 6.64566 14.9362 7.17686 14.9362C7.70806 14.9362 8.21756 14.7255 8.59353 14.3502L17.8055 5.14019C17.9169 5.0047 17.9505 4.9237 17.9841 4.84271C18.0014 4.75588 18.0014 4.66819 18.0014 4.66819C18.0014 4.5805 17.9841 4.49367 17.9505 4.41268C17.9169 4.33169 17.8676 4.25812 17.8055 4.19619C17.7436 4.13401 17.67 4.08467 17.5889 4.051C17.5079 4.01733 17.421 4 17.3332 4C17.2454 4 17.1585 4.01733 17.0775 4.051C16.9964 4.08467 16.9228 4.13401 16.8609 4.19619Z" fill="black"/>
                </svg>
              </div>
              <div>
                <p className="font-dm-sans font-bold text-lg text-black dark:text-white">
                  All actions completed!
                </p>
                <p className="font-dm-sans text-sm text-gray-500 dark:text-white/60 mt-1">
                  Excellent work – check back tomorrow for new smart actions.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* KPI Detail Panel */}
      {selectedKpi && (
        <KpiDetailPanel
          kpiData={selectedKpi}
          onClose={() => setSelectedKpi(null)}
        />
      )}

      {/* Feedback Dialog */}
      <FeedbackDialog
        open={feedbackDialogOpen}
        onSubmit={handleSubmitFeedback}
        onCancel={() => setFeedbackDialogOpen(false)}
      />
    </Layout>
  );
}
