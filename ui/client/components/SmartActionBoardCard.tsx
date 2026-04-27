import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { SmartAction } from "./SmartActionCard";

export type ActionStatus = "pending" | "reminder_set" | "completed" | "couldnt_complete";

export interface SmartActionBoardCardProps {
  action: SmartAction;
  status: ActionStatus;
  reminderTime?: string;
  onExpand: () => void;
  onEditReminder?: () => void;
  isDragging?: boolean;
  isOverlay?: boolean;
  dragHandleProps?: Record<string, unknown>;
}

function ExpandIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
      <path d="M11 3h6v6M17 3l-8 8M8 5H4a1 1 0 00-1 1v10a1 1 0 001 1h10a1 1 0 001-1v-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function CalendarSmallIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674Z" fill="currentColor"/>
    </svg>
  );
}

function DragHandle(props: Record<string, unknown>) {
  return (
    <button
      className="shrink-0 flex items-center justify-center w-6 h-6 rounded text-gray-300 dark:text-white/30 hover:text-gray-500 dark:hover:text-white/60 cursor-grab active:cursor-grabbing touch-none"
      aria-label="Drag to reorder"
      {...props}
    >
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <circle cx="5" cy="3" r="1.5" fill="currentColor"/>
        <circle cx="11" cy="3" r="1.5" fill="currentColor"/>
        <circle cx="5" cy="8" r="1.5" fill="currentColor"/>
        <circle cx="11" cy="8" r="1.5" fill="currentColor"/>
        <circle cx="5" cy="13" r="1.5" fill="currentColor"/>
        <circle cx="11" cy="13" r="1.5" fill="currentColor"/>
      </svg>
    </button>
  );
}

const SmartActionBoardCard = forwardRef<HTMLDivElement, SmartActionBoardCardProps>(
  function SmartActionBoardCard(
    { action, status, reminderTime, onExpand, onEditReminder, isDragging, isOverlay, dragHandleProps },
    ref
  ) {
    return (
      <div
        ref={ref}
        className={cn(
          "flex flex-col gap-3 bg-white dark:bg-white/10 rounded-xl shadow-[0_0_16px_0_rgba(0,0,0,0.08)] p-4 transition-shadow",
          isDragging && "opacity-40 shadow-none",
          isOverlay && "shadow-2xl ring-2 ring-brand-primary/30 rotate-[2deg] scale-105"
        )}
        data-testid="board-card"
      >
        {/* Title row */}
        <div className="flex items-start justify-between gap-2">
          {dragHandleProps && <DragHandle {...dragHandleProps} />}
          <p className="font-dm-sans font-normal text-sm text-black dark:text-white leading-5 flex-1" data-testid="board-card-title">
            {action.title}
          </p>
          <button
            onClick={onExpand}
            className="shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-brand-primary-200 dark:bg-white/10 text-brand-primary dark:text-white hover:bg-brand-primary-100 transition-colors"
            aria-label="View action details"
            data-testid="board-card-expand"
          >
            <ExpandIcon />
          </button>
        </div>

        {/* Reminder badge */}
        {status === "reminder_set" && reminderTime && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-brand-primary-100 dark:bg-white/10 w-fit">
            <span className="text-brand-primary dark:text-white">
              <CalendarSmallIcon />
            </span>
            <span className="font-dm-sans text-xs text-brand-primary dark:text-white/80">
              reminder set for {reminderTime}
            </span>
          </div>
        )}

        {/* Edit reminder button */}
        {status === "reminder_set" && onEditReminder && (
          <button
            onClick={onEditReminder}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-brand-outline-border text-brand-outline-text text-xs font-dm-sans w-fit hover:bg-brand-primary-100 transition-colors"
          >
            <CalendarSmallIcon />
            edit reminder
          </button>
        )}

        {/* Completed / couldn't complete label */}
        {status === "completed" && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-app-lime text-black text-xs font-dm-sans w-fit" data-testid="board-card-status">
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none">
              <path d="M16.86 4.2L7.65 13.41a.75.75 0 01-1.06 0L3.14 9.84a.75.75 0 00-1.06 1.06l3.57 3.56a2.25 2.25 0 003.18 0l9.21-9.21a.75.75 0 00-1.06-1.06z" fill="currentColor"/>
            </svg>
            Completed
          </span>
        )}
        {status === "couldnt_complete" && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-100 text-red-700 text-xs font-dm-sans w-fit" data-testid="board-card-status">
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none">
              <path d="M17.8 2.2a.75.75 0 00-1.06 0L10 8.94 3.26 2.2A.75.75 0 002.2 3.26L8.94 10 2.2 16.74a.75.75 0 101.06 1.06L10 11.06l6.74 6.74a.75.75 0 001.06-1.06L11.06 10l6.74-6.74a.75.75 0 000-1.06z" fill="currentColor"/>
            </svg>
            Couldn't complete
          </span>
        )}
      </div>
    );
  }
);

export default SmartActionBoardCard;
