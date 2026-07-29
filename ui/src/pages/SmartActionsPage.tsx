import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import Layout from "@/components/Layout";
import SmartActionBoardCard, { ActionStatus } from "@/components/SmartActionBoardCard";
import SmartActionCard, {SmartAction} from "@/components/SmartActionCard";
import CompleteActionDialog from "@/components/dialogs/CompleteActionDialog";
import ReminderDialog from "@/components/dialogs/ReminderDialog";
import CouldNotCompleteDialog from "@/components/dialogs/CouldNotCompleteDialog";
import { cn } from "@/lib/utils";
import {
  formatCurrency,
  calculateTotalCost,
} from "@/lib/formatting";
import { useSmartActions } from "@/contexts/SmartActionsContext";
import {
  LightningIcon,
  CalendarDotsIcon,
  CheckIcon,
  BoardViewIcon,
  ListViewIcon,
  ExpandIcon,
  CloseIcon,
} from "@/components/icons";

// ── Date/time display ───────────────────────────────────────────────────────

function DateTimeDisplay() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
  const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const d = now;
  const timeStr = `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
  const dateStr = `${days[d.getDay()]}, ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
  return (
    <div className="flex items-center gap-2 text-black/50 dark:text-white/50">
      <CalendarDotsIcon size={16} className="shrink-0" />
      <span className="font-dm-sans text-sm">{dateStr} &bull; {timeStr}</span>
    </div>
  );
}

// ── Column header ────────────────────────────────────────────────────────────

interface ColumnHeaderProps {
  icon: React.ReactNode;
  title: string;
  count: number;
}

function ColumnHeader({ icon, title, count }: ColumnHeaderProps) {
  return (
    <div className="flex items-center gap-3 pb-4">
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-100 dark:bg-white/10 text-brand-primary dark:text-white shrink-0">
        {icon}
      </div>
      <h2 className="font-bebas text-xl text-black/50 dark:text-white/50 tracking-wide uppercase flex-1">
        {title}
      </h2>
      {count > 0 && (
        <span className="flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded-full bg-brand-primary text-white text-xs font-dm-sans">
          {count}
        </span>
      )}
    </div>
  );
}

// ── Action Detail Panel ──────────────────────────────────────────────────────

interface ActionDetailPanelProps {
  action: SmartAction | null;
  status: ActionStatus;
  onClose: () => void;
  onComplete: (id: number) => void;
  onCouldNotComplete: (id: number) => void;
  onSetReminder: (id: number, time: string) => void;
}

function ActionDetailPanel({
  action,
  status,
  onClose,
  onComplete,
  onCouldNotComplete,
  onSetReminder,
}: ActionDetailPanelProps) {
  const [completeOpen, setCompleteOpen] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [couldNotOpen, setCouldNotOpen] = useState(false);

  if (!action) return null;

  const isDone = status === "completed" || status === "couldnt_complete";
  const reminderSet = status === "reminder_set";

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Slide-in panel */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white dark:bg-gray-900 shadow-2xl flex flex-col overflow-hidden animate-slide-from-right">
        {/* Panel header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-app-neutral-400 dark:border-white/10 shrink-0">
          <div className="flex items-center gap-2 text-brand-primary">
            <LightningIcon size={18} />
            <span className="font-bebas text-lg tracking-wide">Action Detail</span>
          </div>
          <button
            onClick={onClose}
            className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-gray-100 dark:hover:bg-white/10 transition-colors text-gray-500 dark:text-white/60"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-4">
          {/* Title */}
          <h3 className="font-dm-sans font-bold text-base text-black dark:text-white leading-6">
            {action.title}
          </h3>

          {/* Explanation */}
          <div className="flex flex-col gap-3 rounded-2xl border border-app-neutral-400 bg-app-neutral-100 dark:bg-white/5 dark:border-white/10 p-4">
            <p className="font-dm-sans font-bold text-sm text-black dark:text-white">
              Explanation
            </p>
            <ul className="flex flex-col gap-1">
              {action.bullets.map((bullet, i) => (
                <li key={i} className="flex items-start gap-2 font-dm-sans text-sm text-black dark:text-white/80 leading-7">
                  <span className="mt-0.5 shrink-0">•</span>
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
            {action.warning && (
              <div className="flex items-start gap-3 rounded-sm border-l-[8px] border-app-warning bg-white dark:bg-white/10 shadow-toast px-4 py-3">
                <p className="font-dm-sans text-xs text-brand-secondary dark:text-white/90 leading-6">
                  {action.warning}
                </p>
              </div>
            )}
          </div>

          {/* Recommended action */}
          <div className="flex flex-col gap-3 rounded-2xl bg-app-lime p-4">
            <p className="font-dm-sans font-bold text-sm text-black">
              Recommended action
            </p>
            <p className="font-dm-sans text-sm text-black leading-5">
              {action.description}
            </p>
          </div>
        </div>

        {/* Action buttons — fixed at bottom */}
        {!isDone && (
          <div className="shrink-0 px-6 py-4 border-t border-app-neutral-400 dark:border-white/10 flex items-center gap-3 flex-wrap bg-white dark:bg-gray-900">
            <button
              onClick={() => setReminderOpen(true)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-dm-sans transition-colors ${
                reminderSet
                  ? "border-app-lime bg-app-lime text-black"
                  : "border-brand-outline-border text-brand-outline-text hover:bg-brand-primary-100"
              }`}
            >
              <CalendarDotsIcon size={16} />
              {reminderSet ? "Reminder set" : "Set a reminder"}
            </button>
            <button
              onClick={() => setCouldNotOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-full border border-brand-outline-border text-brand-outline-text text-xs font-dm-sans hover:bg-brand-primary-100 transition-colors"
            >
              <CloseIcon size={14} />
              Couldn't complete
            </button>
            <button
              onClick={() => setCompleteOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-brand-primary text-white text-xs font-dm-sans hover:opacity-90 transition-opacity"
            >
              <CheckIcon size={14} />
              Complete
            </button>
          </div>
        )}

        {isDone && (
          <div className="shrink-0 px-6 py-4 border-t border-app-neutral-400 dark:border-white/10 bg-white dark:bg-gray-900">
            <div className={`flex items-center gap-2 px-4 py-2 rounded-full w-fit font-dm-sans text-xs ${
              status === "completed" ? "bg-app-lime text-black" : "bg-red-100 text-red-700"
            }`}>
              {status === "completed" ? "Marked as completed" : "Marked as couldn't complete"}
            </div>
          </div>
        )}
      </div>

      <CompleteActionDialog
        open={completeOpen}
        actionTitle={action.title}
        onConfirm={(_feedback) => { setCompleteOpen(false); onComplete(action.id); onClose(); }}
        onCancel={() => setCompleteOpen(false)}
      />
      <ReminderDialog
        open={reminderOpen}
        actionTitle={action.title}
        onConfirm={(date, time) => {
          setReminderOpen(false);
          onSetReminder(action.id, time);
        }}
        onCancel={() => setReminderOpen(false)}
      />
      <CouldNotCompleteDialog
        open={couldNotOpen}
        actionTitle={action.title}
        onConfirm={(_reason, _comment) => { setCouldNotOpen(false); onCouldNotComplete(action.id); onClose(); }}
        onCancel={() => setCouldNotOpen(false)}
      />
    </>
  );
}

// ── Draggable card wrapper (with touch support) ──────────────────────────────

interface DraggableCardProps {
  action: SmartAction;
  status: ActionStatus;
  reminderTime?: string;
  onExpand: () => void;
  onEditReminder?: () => void;
  onDragStart: (actionId: number) => void;
  onDragEnd: () => void;
  onDrop: (columnKey: string, actionId: number) => void;
  onDragOverColumn: (columnKey: string) => void;
  isDragging: boolean;
}

function DraggableCard({
  action,
  status,
  reminderTime,
  onExpand,
  onEditReminder,
  onDragStart,
  onDragEnd,
  onDrop,
  onDragOverColumn,
  isDragging,
}: DraggableCardProps) {
  const touchStartY = useRef<number>(0);
  const touchStartX = useRef<number>(0);
  const hasMoved = useRef<boolean>(false);

  const handleDragStart = useCallback(
    (e: React.DragEvent) => {
      e.dataTransfer.setData("text/plain", String(action.id));
      e.dataTransfer.effectAllowed = "move";
      onDragStart(action.id);
    },
    [action.id, onDragStart]
  );

  const handleDragEnd = useCallback(() => {
    onDragEnd();
  }, [onDragEnd]);

  // Touch event handlers for mobile support
  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      const touch = e.touches[0];
      touchStartY.current = touch.clientY;
      touchStartX.current = touch.clientX;
      hasMoved.current = false;
    },
    []
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      const touch = e.touches[0];
      const deltaY = Math.abs(touch.clientY - touchStartY.current);
      const deltaX = Math.abs(touch.clientX - touchStartX.current);

      // Only start dragging if moved more than 10px
      if (deltaY > 10 || deltaX > 10) {
        if (!hasMoved.current) {
          hasMoved.current = true;
          onDragStart(action.id);
        }

        // Find which column we're over
        const elements = document.elementsFromPoint(touch.clientX, touch.clientY);
        const columnElement = elements.find((el) =>
          el.hasAttribute('data-column-key')
        );

        if (columnElement) {
          const columnKey = columnElement.getAttribute('data-column-key');
          if (columnKey) {
            onDragOverColumn(columnKey);
          }
        }
      }
    },
    [action.id, onDragStart, onDragOverColumn]
  );

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      if (hasMoved.current) {
        const touch = e.changedTouches[0];
        const elements = document.elementsFromPoint(touch.clientX, touch.clientY);
        const columnElement = elements.find((el) =>
          el.hasAttribute('data-column-key')
        );

        if (columnElement) {
          const columnKey = columnElement.getAttribute('data-column-key');
          if (columnKey) {
            onDrop(columnKey, action.id);
          }
        }
      }
      onDragEnd();
      hasMoved.current = false;
    },
    [action.id, onDrop, onDragEnd]
  );

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      className="cursor-grab active:cursor-grabbing"
    >
      <SmartActionBoardCard
        action={action}
        status={status}
        reminderTime={reminderTime}
        onExpand={onExpand}
        onEditReminder={onEditReminder}
        isDragging={isDragging}
        dragHandleProps={{}}
      />
    </div>
  );
}

// ── Droppable column (native HTML5 drop) ─────────────────────────────────────

interface DroppableColumnProps {
  columnKey: string;
  icon: React.ReactNode;
  title: string;
  actions: SmartAction[];
  isOver: boolean;
  draggingId: number | null;
  onExpand: (action: SmartAction) => void;
  onDragStart: (actionId: number) => void;
  onDragEnd: () => void;
  onDragOverColumn: (columnKey: string) => void;
  onDrop: (columnKey: string, actionId: number) => void;
  onDragLeaveColumn: () => void;
}

function DroppableColumn({
  columnKey,
  icon,
  title,
  actions,
  isOver,
  draggingId,
  onExpand,
  onDragStart,
  onDragEnd,
  onDragOverColumn,
  onDrop,
  onDragLeaveColumn,
}: DroppableColumnProps) {
  const { getActionStatus, actionStates } = useSmartActions();
  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      onDragOverColumn(columnKey);
    },
    [columnKey, onDragOverColumn]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const actionId = parseInt(e.dataTransfer.getData("text/plain"), 10);
      if (!isNaN(actionId)) {
        onDrop(columnKey, actionId);
      }
    },
    [columnKey, onDrop]
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      if (e.currentTarget === e.target || !e.currentTarget.contains(e.relatedTarget as Node)) {
        onDragLeaveColumn();
      }
    },
    [onDragLeaveColumn]
  );

  return (
    <div
      data-column-key={columnKey}
      className={cn(
        "flex flex-col min-h-0 rounded-2xl p-4 shadow-[0_1px_16px_0_rgba(0,0,0,0.06)] transition-colors duration-200",
        isOver
          ? "bg-brand-primary/10 dark:bg-brand-primary/20 ring-2 ring-brand-primary/30 ring-inset"
          : "bg-white/60 dark:bg-white/5"
      )}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onDragLeave={handleDragLeave}
    >
      <ColumnHeader icon={icon} title={title} count={actions.length} />
      <div className="h-px bg-black/10 dark:bg-white/10 mb-4" />

      <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-0.5 min-h-[60px]">
        {actions.length === 0 ? (
          <div className={cn(
            "flex flex-col items-center justify-center gap-2 py-10 text-center transition-opacity",
            isOver ? "opacity-60" : "opacity-40"
          )}>
            <div className="w-8 h-8 text-gray-400 dark:text-white/40">{icon}</div>
            <p className="font-dm-sans text-xs text-gray-400 dark:text-white/40">
              {isOver ? "Drop here" : "No actions here yet"}
            </p>
          </div>
        ) : (
          actions.map((action) => {
            const state = actionStates.get(action.id);
            return (
              <DraggableCard
                key={action.id}
                action={action}
                status={getActionStatus(action.id)}
                reminderTime={state?.reminderDate?.toISOString()}
                onExpand={() => onExpand(action)}
                onEditReminder={() => onExpand(action)}
                onDragStart={onDragStart}
                onDragEnd={onDragEnd}
                onDrop={onDrop}
                onDragOverColumn={onDragOverColumn}
                isDragging={draggingId === action.id}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

// ── Map column keys to statuses ──────────────────────────────────────────────

const COLUMN_STATUS_MAP: Record<string, ActionStatus> = {
  pending: "pending",
  reminder_set: "reminder_set",
  done: "completed",
};

// ── List view helpers ─────────────────────────────────────────────────────────

type FilterKey = "all" | "scheduled" | "completed" | "couldnt_complete";

// ── List View Content ─────────────────────────────────────────────────────────

interface ListViewContentProps {
  allActions: SmartAction[];
}

function ListViewContent({ allActions }: ListViewContentProps) {
  const { getActionStatus } = useSmartActions();
  const [activeFilter, setActiveFilter] = useState<FilterKey>("all");

  const counts = useMemo(() => {
    const result = { all: allActions.length, scheduled: 0, completed: 0, couldnt_complete: 0 };
    allActions.forEach((action) => {
      const s = getActionStatus(action.id);
      if (s === "completed") result.completed++;
      else if (s === "couldnt_complete") result.couldnt_complete++;
      else if (s === "reminder_set") result.scheduled++;
    });
    return result;
  }, [allActions, getActionStatus]);

  const filteredActions = useMemo(() => {
    return allActions.filter((action) => {
      if (activeFilter === "all") return true;
      const s = getActionStatus(action.id);
      if (activeFilter === "scheduled") return s === "reminder_set";
      if (activeFilter === "completed") return s === "completed";
      if (activeFilter === "couldnt_complete") return s === "couldnt_complete";
      return false;
    });
  }, [allActions, activeFilter, getActionStatus]);

  const pendingCount = allActions.filter((a) => {
    const s = getActionStatus(a.id);
    return s !== "completed" && s !== "couldnt_complete" && s !== "reminder_set";
  }).length;

  const filterBadges: { key: FilterKey; label: string }[] = [
    { key: "all", label: `All (${counts.all})` },
    { key: "scheduled", label: `Scheduled (${counts.scheduled})` },
    { key: "completed", label: `Completed (${counts.completed})` },
    { key: "couldnt_complete", label: `Couldn't complete (${counts.couldnt_complete})` },
  ];

  return (
    <div className="flex flex-col gap-6 rounded-2xl bg-white/20 dark:bg-white/5 p-6 shadow-[1px_1px_16px_0_rgba(0,0,0,0.08)]">
      {/* Section header row */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center justify-center w-9 h-9 rounded-full bg-brand-primary-100 dark:bg-white/10 shrink-0">
          <LightningIcon size={20} />
        </div>
        <h2 className="font-bebas text-3xl text-black/50 dark:text-white/50 tracking-wide">
          Today's Next Best Actions
        </h2>
        <span className="flex items-center px-4 py-1 rounded-full bg-app-lime font-dm-sans text-sm text-black whitespace-nowrap">
          {pendingCount} priority action{pendingCount !== 1 ? "s" : ""} worth {formatCurrency(calculateTotalCost(allActions))}
        </span>
        {/* Filter badges */}
        <div className="flex items-center gap-2 flex-wrap ml-auto">
          {filterBadges.map((badge) => (
            <button
              key={badge.key}
              onClick={() => setActiveFilter(badge.key)}
              className={cn(
                "px-3 py-1 rounded-full font-dm-sans text-xs font-medium transition-colors whitespace-nowrap",
                activeFilter === badge.key
                  ? "bg-brand-primary text-white"
                  : "bg-brand-primary-200 text-black dark:bg-white/10 dark:text-white/80 hover:opacity-80"
              )}
            >
              {badge.label}
            </button>
          ))}
        </div>
      </div>

      {/* Flat filtered action list */}
      {filteredActions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <p className="font-dm-sans text-sm text-gray-500 dark:text-white/60">
            No actions in this category
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {filteredActions.map((action) => (
            <SmartActionCard key={action.id} action={action} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SmartActionsPage() {
  const {
    actions: allActions,
    actionStates,
    updateActionStatus,
    getActionStatus,
    getActionsByStatus
  } = useSmartActions();

  const [expandedAction, setExpandedAction] = useState<SmartAction | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [overColumnKey, setOverColumnKey] = useState<string | null>(null);
  const [reminderActionId, setReminderActionId] = useState<number | null>(null);
  const [completionActionId, setCompletionActionId] = useState<number | null>(null);
  const [showCompleteDialog, setShowCompleteDialog] = useState(false);
  const [showCouldNotCompleteDialog, setShowCouldNotCompleteDialog] = useState(false);
  const [viewMode, setViewMode] = useState<"board" | "list">("list");

  const handleComplete = (id: number) => {
    updateActionStatus(id, "completed");
  };

  const handleCouldNotComplete = (id: number) => {
    updateActionStatus(id, "couldnt_complete");
  };

  const handleSetReminder = (id: number, time: string) => {
    const reminderDate = new Date(time);
    updateActionStatus(id, "reminder_set", reminderDate);
  };

  const handleDragReminderConfirm = (date: string, time: string) => {
    if (reminderActionId) {
      const reminderDate = new Date(`${date}T${time}`);
      updateActionStatus(reminderActionId, "reminder_set", reminderDate);
      setReminderActionId(null);
    }
  };

  const handleDragReminderCancel = () => {
    setReminderActionId(null);
  };

  const handleChooseComplete = () => {
    setShowCompleteDialog(true);
  };

  const handleChooseCouldNotComplete = () => {
    setShowCouldNotCompleteDialog(true);
  };

  const handleDragCompleteConfirm = (feedback: string) => {
    if (completionActionId) {
      updateActionStatus(completionActionId, "completed");
      setCompletionActionId(null);
      setShowCompleteDialog(false);
    }
  };

  const handleDragCompleteCancel = () => {
    setCompletionActionId(null);
    setShowCompleteDialog(false);
  };

  const handleDragCouldNotCompleteConfirm = (reason: string, comment: string) => {
    if (completionActionId) {
      updateActionStatus(completionActionId, "couldnt_complete");
      setCompletionActionId(null);
      setShowCouldNotCompleteDialog(false);
    }
  };

  const handleDragCouldNotCompleteCancel = () => {
    setCompletionActionId(null);
    setShowCouldNotCompleteDialog(false);
  };

  const handleDragStart = useCallback((actionId: number) => {
    setDraggingId(actionId);
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggingId(null);
    setOverColumnKey(null);
  }, []);

  const handleDragOverColumn = useCallback((columnKey: string) => {
    setOverColumnKey(columnKey);
  }, []);

  const handleDragLeaveColumn = useCallback(() => {
    setOverColumnKey(null);
  }, []);

  const handleDrop = useCallback(
    (columnKey: string, actionId: number) => {
      setDraggingId(null);
      setOverColumnKey(null);

      const newStatus = COLUMN_STATUS_MAP[columnKey];
      if (!newStatus) return;
      if (getActionStatus(actionId) === newStatus) return;

      // If dropping into reminder_set column, show the reminder dialog
      if (columnKey === "reminder_set") {
        setReminderActionId(actionId);
        return;
      }

      // If dropping into done column, show choice dialog
      if (columnKey === "done") {
        setCompletionActionId(actionId);
        return;
      }

      updateActionStatus(actionId, newStatus);
    },
    [updateActionStatus, getActionStatus]
  );

  // Recalculate columns whenever actionStates changes
  const columns = useMemo(() => {
    const pendingActions = getActionsByStatus("pending");
    const reminderActions = getActionsByStatus("reminder_set");
    const completedActions = getActionsByStatus("completed");
    const couldNotCompleteActions = getActionsByStatus("couldnt_complete");
    const doneActions = [...completedActions, ...couldNotCompleteActions];

    return [
      {
        key: "pending",
        icon: <LightningIcon size={16} />,
        title: "Today's Next Best Actions",
        actions: pendingActions,
      },
      {
        key: "reminder_set",
        icon: <CalendarDotsIcon size={16} />,
        title: "Reminder Set",
        actions: reminderActions,
      },
      {
        key: "done",
        icon: <CheckIcon size={16} />,
        title: "Complete / Couldn't Complete",
        actions: doneActions,
      },
    ];
  }, [actionStates, getActionsByStatus]);

  return (
    <Layout>
      {/* Page header */}
      <div className="px-5 md:px-8 pt-6 pb-4 pl-16 md:pl-8 shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h1 className="font-bebas text-[32px] text-black dark:text-white tracking-wide">
            smart action status
          </h1>
          {/* View mode toggle */}
          <div className="flex items-center gap-2 bg-white dark:bg-white/10 rounded-lg p-1 shrink-0 overflow-hidden">
            <button
              onClick={() => setViewMode("board")}
              className={cn(
                "flex items-center gap-1 px-3 py-2 rounded-lg transition-colors overflow-hidden",
                viewMode === "board"
                  ? "bg-brand-primary text-white"
                  : "text-gray-600 dark:text-white/60 hover:text-gray-900 dark:hover:text-white"
              )}
              title="Board view"
            >
              <BoardViewIcon size={18} />
              <span className="text-xs font-medium hidden sm:inline">Board</span>
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={cn(
                "flex items-center gap-1 px-3 py-2 rounded-lg transition-colors overflow-hidden",
                viewMode === "list"
                  ? "bg-brand-primary text-white"
                  : "text-gray-600 dark:text-white/60 hover:text-gray-900 dark:hover:text-white"
              )}
              title="List view"
            >
              <ListViewIcon size={18} />
              <span className="text-xs font-medium hidden sm:inline">List</span>
            </button>
          </div>
        </div>
        <DateTimeDisplay />
      </div>

      {/* Board/List view */}
      {viewMode === "board" ? (
        // Board with native drag-and-drop
        <div className="flex-1 overflow-y-auto md:overflow-hidden px-5 md:px-8 pb-8 min-h-0">
          <div className="h-full grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 md:min-h-0">
            {columns.map((col) => (
              <DroppableColumn
                key={col.key}
                columnKey={col.key}
                icon={col.icon}
                title={col.title}
                actions={col.actions}
                isOver={overColumnKey === col.key}
                draggingId={draggingId}
                onExpand={setExpandedAction}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                onDragOverColumn={handleDragOverColumn}
                onDrop={handleDrop}
                onDragLeaveColumn={handleDragLeaveColumn}
              />
            ))}
          </div>
        </div>
      ) : (
        // List view with status filter badges and detailed action cards
        <div className="flex-1 overflow-y-auto px-5 md:px-8 pb-8">
          <ListViewContent
            allActions={allActions}
          />
        </div>
      )}

      {/* Detail panel */}
      {expandedAction && (
        <ActionDetailPanel
          action={expandedAction}
          status={getActionStatus(expandedAction.id)}
          onClose={() => setExpandedAction(null)}
          onComplete={handleComplete}
          onCouldNotComplete={handleCouldNotComplete}
          onSetReminder={handleSetReminder}
        />
      )}

      {/* Reminder dialog for drag-to-reminder */}
      {reminderActionId && (
        <ReminderDialog
          open={true}
          actionTitle={allActions.find(a => a.id === reminderActionId)?.title || ""}
          onConfirm={handleDragReminderConfirm}
          onCancel={handleDragReminderCancel}
        />
      )}

      {/* Choice dialog for drag-to-done */}
      {completionActionId && !showCompleteDialog && !showCouldNotCompleteDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setCompletionActionId(null)} />
          <div className="relative bg-white dark:bg-gray-900 rounded-2xl shadow-action p-6 max-w-md w-full mx-4">
            <h2 className="font-dm-sans font-bold text-lg text-black dark:text-white mb-2">
              How did this action go?
            </h2>
            <p className="font-dm-sans text-sm text-gray-600 dark:text-white/60 mb-6">
              Please let us know the outcome for "<span className="font-semibold text-black dark:text-white">
                {allActions.find(a => a.id === completionActionId)?.title}
              </span>"
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={handleChooseComplete}
                className="w-full px-4 py-3 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity"
              >
                Mark as Complete
              </button>
              <button
                onClick={handleChooseCouldNotComplete}
                className="w-full px-4 py-3 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors"
              >
                Couldn't Complete
              </button>
              <button
                onClick={() => setCompletionActionId(null)}
                className="w-full px-4 py-2 text-sm font-dm-sans text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Complete dialog for drag-to-done */}
      {showCompleteDialog && completionActionId && (
        <CompleteActionDialog
          open={true}
          actionTitle={allActions.find(a => a.id === completionActionId)?.title || ""}
          onConfirm={handleDragCompleteConfirm}
          onCancel={handleDragCompleteCancel}
        />
      )}

      {/* Could not complete dialog for drag-to-done */}
      {showCouldNotCompleteDialog && completionActionId && (
        <CouldNotCompleteDialog
          open={true}
          actionTitle={allActions.find(a => a.id === completionActionId)?.title || ""}
          onConfirm={handleDragCouldNotCompleteConfirm}
          onCancel={handleDragCouldNotCompleteCancel}
        />
      )}
    </Layout>
  );
}
