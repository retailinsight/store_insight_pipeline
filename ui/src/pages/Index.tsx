import { useEffect, useRef, useState } from "react";
import { MessageCircle } from "lucide-react";
import Layout from "@/components/Layout";
import KpiWidget from "@/components/KpiWidget";
import SuccessCard from "@/components/SuccessCard";
import SmartActionCard from "@/components/SmartActionCard";
import KpiDetailPanel from "@/components/KpiDetailPanel";
import FeedbackDialog from "@/components/dialogs/FeedbackDialog";
import { useSmartActions } from "@/contexts/SmartActionsContext";
import {
  formatDateTime,
  formatCurrency,
  calculateTotalCost,
} from "@/lib/formatting";
import {
  MedalIcon,
  LightningIcon,
  CalendarDotsIcon,
  CheckBoldIcon,
} from "@/components/icons";
import { useToast } from "@/hooks/useToast";
import { KpiData } from "@/models";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { fetchKpisThunk } from "@/store/slices/kpisSlice";
import { fetchSuccessesThunk } from "@/store/slices/successesSlice";
import { selectStore as selectStoreAction } from "@/store/slices/authSlice";
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
      trend: kpi.trendDirection,
      clusterAvg: kpi.clusterAverage,
      icon,
    };
  });
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

  const { toast } = useToast();
  const dispatch = useAppDispatch();

  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated);
  const selectedStore = useAppSelector((s) => s.auth.selectedStore);
  const availableStores = useAppSelector((s) => s.auth.availableStores);
  const selectStore = (store: (typeof availableStores)[number]) =>
    dispatch(selectStoreAction(store));

  const {
    data: kpisData,
    isLoading: kpisLoading,
    error: kpisError,
  } = useAppSelector((s) => s.kpis);
  const {
    data: successesData,
    isLoading: successesLoading,
    error: successesError,
  } = useAppSelector((s) => s.successes);

  const [now, setNow] = useState(new Date());
  const [selectedKpi, setSelectedKpi] = useState<KpiData | null>(null);
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);
  const lastKpisError = useRef<string | null>(null);
  const lastSuccessesError = useRef<string | null>(null);

  // Trigger KPI refresh when auth or selected store changes.
  useEffect(() => {
    if (!isAuthenticated || !selectedStore?.id) return;
    dispatch(fetchKpisThunk());
  }, [dispatch, isAuthenticated, selectedStore?.id]);

  // Successes does not depend on storeId.
  useEffect(() => {
    if (!isAuthenticated) return;
    dispatch(fetchSuccessesThunk());
  }, [dispatch, isAuthenticated]);

  // Surface fetch errors via toast (skip session-expired which is handled globally).
  useEffect(() => {
    if (
      kpisError &&
      kpisError !== lastKpisError.current &&
      kpisError !== "SESSION_EXPIRED"
    ) {
      lastKpisError.current = kpisError;
      toast({
        title: "Failed to load KPI data",
        description: kpisError,
        variant: "destructive",
      });
    }
    if (!kpisError) lastKpisError.current = null;
  }, [kpisError, toast]);

  useEffect(() => {
    if (
      successesError &&
      successesError !== lastSuccessesError.current &&
      successesError !== "SESSION_EXPIRED"
    ) {
      lastSuccessesError.current = successesError;
      toast({
        title: "Failed to load success data",
        description: successesError,
        variant: "destructive",
      });
    }
    if (!successesError) lastSuccessesError.current = null;
  }, [successesError, toast]);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const actions = getVisibleActions();
  const completedActions = getActionsByStatus("completed");
  const couldNotCompleteActions = getActionsByStatus("couldnt_complete");
  const completedCount =
    completedActions.length + couldNotCompleteActions.length;
  const totalActions = allActions.length;
  const progressPct = Math.round((completedCount / totalActions) * 100);

  return (
    <Layout>
      {/* Page header — on mobile add left padding to clear the hamburger button */}
      <div
        className="px-5 md:px-8 pt-6 pb-4 pl-16 md:pl-8 shrink-0 flex flex-col gap-1 animate-panel-in opacity-0"
        style={{ animationDelay: "100ms" }}
      >
        <div className="flex items-center justify-between">
          <h1 className="font-bebas text-[32px] text-black dark:text-white tracking-wide">
            Store {selectedStore?.id}: {selectedStore?.name}
          </h1>
          <div className="flex items-center gap-3">
            {/* <button
              onClick={() => setFeedbackDialogOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors md:px-4"
              title="Send us your feedback"
            >
              <MessageCircle size={18} />
              <span className="hidden md:inline">Send feedback</span>
            </button> */}
            {availableStores.length > 1 && (
              <div className="flex items-center gap-2">
                <span className="font-dm-sans text-sm text-gray-600 dark:text-white/60">
                  Switch store:
                </span>
                <Select
                  value={String(selectedStore?.id || "")}
                  onValueChange={(storeId) => {
                    const selected = availableStores.find(
                      (s) => String(s.id) === storeId,
                    );
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
                      <SelectItem
                        className="cursor-pointer"
                        key={store.id}
                        value={String(store.id)}
                      >
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
          <CalendarDotsIcon size={16} className="shrink-0" />
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
              {[1, 2].map((i) => (
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
            kpisData
              .filter((kpi) => {
                const name = kpi.name.toLowerCase();
                return name.includes("availability") || name.includes("waste");
              })
              .map((kpi, i) => {
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
        <section
          className="flex flex-col gap-6 rounded-2xl bg-white dark:bg-white/5 pt-4 px-6 pb-4 shadow-[1px_1px_16px_0_rgba(0,0,0,0.08)] animate-panel-in opacity-0"
          style={{ animationDelay: "500ms" }}
        >
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
                  triggerTypes={s.triggerTypes}
                  type={s.type}
                  value={s.value}
                  trendDirection={s.trendDirection}
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
        <section
          className="flex flex-col gap-6 rounded-2xl bg-white/20 dark:bg-white/5 p-6 shadow-[1px_1px_16px_0_rgba(0,0,0,0.08)] animate-panel-in opacity-0"
          style={{ animationDelay: "700ms" }}
        >
          {/* Header */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-brand-primary-100">
              <LightningIcon />
            </div>
            <h2 className="font-bebas text-3xl text-black/50 dark:text-white/50 tracking-wide">
              Today's Next Best Actions
            </h2>
            <span className="flex items-center px-4 py-1 rounded-full bg-app-lime font-dm-sans text-sm text-black">
              {actions.length} priority action{actions.length !== 1 ? "s" : ""}{" "}
              worth {formatCurrency(calculateTotalCost(allActions))}
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
                <SmartActionCard key={action.id} action={action} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4 py-12 text-center">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-app-lime">
                <CheckBoldIcon size={32} className="text-black" />
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
        onClose={() => setFeedbackDialogOpen(false)}
      />
    </Layout>
  );
}
