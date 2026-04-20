import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import Layout from "@/components/Layout";
import SmartActionBoardCard, { ActionStatus } from "@/components/SmartActionBoardCard";
import SmartActionCard, { SmartAction } from "@/components/SmartActionCard";
import CompleteActionDialog from "@/components/dialogs/CompleteActionDialog";
import ReminderDialog from "@/components/dialogs/ReminderDialog";
import CouldNotCompleteDialog from "@/components/dialogs/CouldNotCompleteDialog";
import { cn } from "@/lib/utils";
import { useSmartActions } from "@/contexts/SmartActionsContext";

// ── Icons ────────────────────────────────────────────────────────────────────

function LightningIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12.5658 24H8.71882L10.7188 16H6.58582C6.18639 15.9998 5.79255 15.9062 5.43575 15.7267C5.07894 15.5472 4.76908 15.2867 4.53092 14.966C4.29276 14.6454 4.13291 14.2734 4.06413 13.88C3.99535 13.4865 4.01956 13.0824 4.13482 12.7L7.97582 0H17.4428L14.4428 8H18.4658C18.9235 8.00029 19.3726 8.1246 19.7653 8.35972C20.1581 8.59484 20.4797 8.93197 20.6962 9.33529C20.9126 9.73861 21.0157 10.193 20.9945 10.6503C20.9733 11.1075 20.8286 11.5504 20.5758 11.932L12.5658 24ZM11.2808 22H11.4928L18.9088 10.826C18.962 10.7459 18.9924 10.6528 18.9969 10.5568C19.0013 10.4607 18.9797 10.3653 18.9343 10.2806C18.8888 10.1958 18.8213 10.125 18.7388 10.0756C18.6563 10.0262 18.562 10.0001 18.4658 10H11.5568L14.5568 2H9.45982L6.04882 13.276C6.02336 13.3599 6.01789 13.4485 6.03286 13.5348C6.04784 13.6212 6.08283 13.7028 6.13503 13.7732C6.18724 13.8436 6.2552 13.9008 6.33348 13.9401C6.41177 13.9795 6.49819 14 6.58582 14H13.2858L11.2808 22Z" fill="#577DF7"/>
    </svg>
  );
}

function CalendarIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674ZM12.3343 12.0001C12.3343 11.4475 12.7816 11.0002 13.3342 11.0002C13.8859 11.0002 14.3341 11.4475 14.3341 12.0001C14.3341 12.5518 13.8859 13 13.3342 13C12.7816 13 12.3343 12.5518 12.3343 12.0001ZM9.00051 12.0001C9.00051 11.4475 9.44783 11.0002 10.0005 11.0002C10.5531 11.0002 11.0004 11.4475 11.0004 12.0001C11.0004 12.5518 10.5531 13 10.0005 13C9.44783 13 9.00051 12.5518 9.00051 12.0001ZM5.66676 12.0001C5.66676 11.4475 6.11498 11.0002 6.6667 11.0002C7.21933 11.0002 7.66665 11.4475 7.66665 12.0001C7.66665 12.5518 7.21933 13 6.6667 13C6.11498 13 5.66676 12.5518 5.66676 12.0001Z" fill="currentColor"/>
    </svg>
  );
}

function CheckIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <path d="M16.8609 4.19619L7.64819 13.4082C7.58625 13.4704 7.51264 13.5197 7.43159 13.5534C7.35053 13.5871 7.26363 13.6044 7.17586 13.6044C7.08809 13.6044 7.00118 13.5871 6.92013 13.5534C6.83908 13.5197 6.76547 13.4704 6.70353 13.4082L3.14086 9.84219C2.99963 9.70097 2.92058 9.50937 2.92058 9.30975C2.92058 9.11013 2.99963 8.91853 3.14086 8.7773C3.28208 8.63608 3.47369 8.55703 3.67331 8.55703C3.87292 8.55703 4.06453 8.63608 4.20575 8.7773L7.17586 11.7481L15.7961 3.12784C15.9374 2.98661 16.129 2.90756 16.3286 2.90756C16.5282 2.90756 16.7198 2.98661 16.8609 3.12784C17.0021 3.26907 17.0812 3.46067 17.0812 3.66029C17.0812 3.85991 17.0021 4.05151 16.8609 4.19274V4.19619Z" fill="currentColor"/>
    </svg>
  );
}

function BoardViewIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M3 3H9V9H3V3ZM11 3H17V9H11V3ZM15 11H17V17H15V11ZM3 11H9V17H3V11ZM11 15H13V17H11V15Z" fill="currentColor" stroke="currentColor" strokeWidth="0.5"/>
    </svg>
  );
}

function ListViewIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M3 4H21V6H3V4ZM3 10H21V12H3V10ZM3 16H21V18H3V16Z" fill="currentColor"/>
    </svg>
  );
}

function ExpandIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
      <path d="M11 3h6v6M17 3l-8 8M8 5H4a1 1 0 00-1 1v10a1 1 0 001 1h10a1 1 0 001-1v-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

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
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
        <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674ZM12.3343 12.0001C12.3343 11.4475 12.7816 11.0002 13.3342 11.0002C13.8859 11.0002 14.3341 11.4475 14.3341 12.0001C14.3341 12.5518 13.8859 13 13.3342 13C12.7816 13 12.3343 12.5518 12.3343 12.0001ZM9.00051 12.0001C9.00051 11.4475 9.44783 11.0002 10.0005 11.0002C10.5531 11.0002 11.0004 11.4475 11.0004 12.0001C11.0004 12.5518 10.5531 13 10.0005 13C9.44783 13 9.00051 12.5518 9.00051 12.0001ZM5.66676 12.0001C5.66676 11.4475 6.11498 11.0002 6.6667 11.0002C7.21933 11.0002 7.66665 11.4475 7.66665 12.0001C7.66665 12.5518 7.21933 13 6.6667 13C6.11498 13 5.66676 12.5518 5.66676 12.0001Z" fill="currentColor"/>
      </svg>
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
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
              <path d="M17.805 2.197a.75.75 0 00-1.061 0L10 8.94 3.256 2.197a.75.75 0 00-1.061 1.06L8.94 10l-6.744 6.743a.75.75 0 001.06 1.061L10 11.06l6.744 6.744a.75.75 0 001.06-1.06L11.06 10l6.744-6.744a.75.75 0 000-1.06z" fill="currentColor"/>
            </svg>
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
              <CalendarIcon size={16} />
              {reminderSet ? "Reminder set" : "Set a reminder"}
            </button>
            <button
              onClick={() => setCouldNotOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-full border border-brand-outline-border text-brand-outline-text text-xs font-dm-sans hover:bg-brand-primary-100 transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
                <path d="M17.805 2.197a.75.75 0 00-1.061 0L10 8.94 3.256 2.197a.75.75 0 00-1.061 1.06L8.94 10l-6.744 6.743a.75.75 0 001.06 1.061L10 11.06l6.744 6.744a.75.75 0 001.06-1.06L11.06 10l6.744-6.744a.75.75 0 000-1.06z" fill="currentColor"/>
              </svg>
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

function calculateTotalCost(actions: SmartAction[]): number {
  return actions.reduce((total, action) => {
    if (!action.warning) return total;
    const match = action.warning.match(/£([\d,]+\.?\d*)/);
    if (match) {
      return total + parseFloat(match[1].replace(/,/g, ""));
    }
    return total;
  }, 0);
}

function formatCurrency(amount: number): string {
  return "£" + amount.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

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
        icon: <CalendarIcon size={16} />,
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
