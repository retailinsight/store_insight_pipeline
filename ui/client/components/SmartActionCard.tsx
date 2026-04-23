import { useState } from "react";
import { cn } from "@/lib/utils";
import CompleteActionDialog from "./dialogs/CompleteActionDialog";
import ReminderDialog from "./dialogs/ReminderDialog";
import CouldNotCompleteDialog from "./dialogs/CouldNotCompleteDialog";
import { useSmartActions } from "@/contexts/SmartActionsContext";
import { completeAction as completeActionApi } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export interface SmartAction {
  id: number;
  title: string;
  description: string;
  bullets: string[];
  warning?: string;
  badges?: {
    section: string;
    type: string;
  };
  recommendedAction?: string;
}

interface SmartActionCardProps {
  action: SmartAction;
  onComplete?: (id: number) => void;
}

function CalendarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
      <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674ZM12.3343 12.0001C12.3343 11.4475 12.7816 11.0002 13.3342 11.0002C13.8859 11.0002 14.3341 11.4475 14.3341 12.0001C14.3341 12.5518 13.8859 13 13.3342 13C12.7816 13 12.3343 12.5518 12.3343 12.0001ZM9.00051 12.0001C9.00051 11.4475 9.44783 11.0002 10.0005 11.0002C10.5531 11.0002 11.0004 11.4475 11.0004 12.0001C11.0004 12.5518 10.5531 13 10.0005 13C9.44783 13 9.00051 12.5518 9.00051 12.0001ZM5.66676 12.0001C5.66676 11.4475 6.11498 11.0002 6.6667 11.0002C7.21933 11.0002 7.66665 11.4475 7.66665 12.0001C7.66665 12.5518 7.21933 13 6.6667 13C6.11498 13 5.66676 12.5518 5.66676 12.0001Z" fill="currentColor"/>
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
      <path d="M17.805 2.19673C17.545 1.93573 17.123 1.93573 16.862 2.19673L10 9.05873L3.13801 2.19673C2.878 1.93573 2.45599 1.93573 2.19499 2.19673C1.93501 2.45672 1.93501 2.87874 2.19499 3.13873L9.05799 10.0007L2.19499 16.8627C1.93501 17.1237 1.93501 17.5457 2.19499 17.8057C2.45601 18.0657 2.878 18.0657 3.13801 17.8057L10 10.9437L16.862 17.8057C17.123 18.0657 17.545 18.0657 17.805 17.8057C18.065 17.5457 18.065 17.1237 17.805 16.8627L10.943 10.0007L17.805 3.13873C18.065 2.87874 18.065 2.45672 17.805 2.19673Z" fill="currentColor"/>
    </svg>
  );
}

function TickIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
      <path d="M16.8609 4.19619L7.64819 13.4082C7.58625 13.4704 7.51264 13.5197 7.43159 13.5534C7.35053 13.5871 7.26363 13.6044 7.17586 13.6044C7.08809 13.6044 7.00118 13.5871 6.92013 13.5534C6.83908 13.5197 6.76547 13.4704 6.70353 13.4082L3.14086 9.84219C3.07892 9.78001 3.00531 9.73067 2.92426 9.697C2.8432 9.66333 2.7563 9.646 2.66853 9.646C2.58076 9.646 2.49385 9.66333 2.4128 9.697C2.33174 9.73067 2.25813 9.78001 2.19619 9.84219C2.13401 9.90413 2.08467 9.97774 2.051 10.0588C2.01733 10.1399 2 10.2268 2 10.3145C2 10.4023 2.01733 10.4892 2.051 10.5703C2.08467 10.6513 2.13401 10.7249 2.19619 10.7869L5.76019 14.3502C6.13616 14.7255 6.64566 14.9362 7.17686 14.9362C7.70806 14.9362 8.21756 14.7255 8.59353 14.3502L17.8055 5.14019C17.8676 5.07827 17.9169 5.0047 17.9505 4.9237C17.9841 4.84271 18.0014 4.75588 18.0014 4.66819C18.0014 4.5805 17.9841 4.49367 17.9505 4.41268C17.9169 4.33169 17.8676 4.25812 17.8055 4.19619C17.7436 4.13401 17.67 4.08467 17.5889 4.051C17.5079 4.01733 17.421 4 17.3332 4C17.2454 4 17.1585 4.01733 17.0775 4.051C16.9964 4.08467 16.9228 4.13401 16.8609 4.19619Z" fill="currentColor"/>
    </svg>
  );
}


export default function SmartActionCard({ action, onComplete }: SmartActionCardProps) {
  const { updateActionStatus, getActionStatus } = useSmartActions();
  const [completeDialogOpen, setCompleteDialogOpen] = useState(false);
  const [reminderDialogOpen, setReminderDialogOpen] = useState(false);
  const [couldNotCompleteDialogOpen, setCouldNotCompleteDialogOpen] = useState(false);
  const { toast } = useToast();

  const status = getActionStatus(action.id);
  const reminderSet = status === "reminder_set";

  const handleComplete = async (opinion: "positive" | "negative", feedback: string) => {
    try {
      await completeActionApi(action.id, opinion, feedback);
      setCompleteDialogOpen(false);
      updateActionStatus(action.id, "completed");
      toast({
        title: "Action completed",
        description: "Thanks for your feedback!",
      });
      onComplete?.(action.id);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to complete action";
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  const handleReminder = (date: string, time: string, method: string) => {
    setReminderDialogOpen(false);
    const reminderDate = new Date(`${date}T${time}`);
    updateActionStatus(action.id, "reminder_set", reminderDate);
  };

  const handleCouldNotComplete = (reason: string, comment: string) => {
    setCouldNotCompleteDialogOpen(false);
    updateActionStatus(action.id, "couldnt_complete");
    onComplete?.(action.id);
  };

  return (
    <>
      <div className="flex flex-col gap-4 bg-white dark:bg-white/10 rounded-2xl border border-[#D3D3D3] dark:border-white/10 shadow-[0_0_24px_0_rgba(0,0,0,0.08)] p-6 animate-slide-in">

        {/* Badges */}
        {action.badges && (
          <div className="flex gap-2 flex-wrap">
            <span className="px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-dm-sans font-medium">
              {action.badges.section}
            </span>
            <span className="px-3 py-1 rounded-full bg-purple-100 text-purple-700 text-xs font-dm-sans font-medium">
              {action.badges.type}
            </span>
          </div>
        )}

        {/* Header */}
        <h3 className="font-dm-sans font-bold text-base text-black dark:text-white leading-5">
          {action.title}
        </h3>

        {/* Explanation section: bullets + warning */}
        <div className="flex flex-col gap-3">
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

        {/* Recommended action section */}
        <div className="flex flex-col gap-3 rounded-2xl bg-app-lime p-4">
          <p className="font-dm-sans font-bold text-sm text-black">
            Recommended action
          </p>
          <p className="font-dm-sans text-sm text-black leading-5">
            {action.recommendedAction || action.description}
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 flex-wrap justify-end">
          <button
            onClick={() => setReminderDialogOpen(true)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-dm-sans transition-colors",
              reminderSet
                ? "border-app-lime bg-app-lime text-black"
                : "border-brand-outline-border text-brand-outline-text hover:bg-brand-primary-100"
            )}
          >
            <CalendarIcon />
            {reminderSet ? "Reminder set" : "Set a reminder"}
          </button>

          <button
            onClick={() => setCouldNotCompleteDialogOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-full border border-brand-outline-border text-brand-outline-text text-xs font-dm-sans hover:bg-brand-primary-100 transition-colors"
          >
            <CloseIcon />
            Couldn't complete
          </button>

          <button
            onClick={() => setCompleteDialogOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-brand-primary text-white text-xs font-dm-sans hover:opacity-90 transition-opacity"
          >
            <TickIcon />
            Mark Complete
          </button>
        </div>
      </div>

      <CompleteActionDialog
        open={completeDialogOpen}
        actionTitle={action.title}
        onConfirm={handleComplete}
        onCancel={() => setCompleteDialogOpen(false)}
      />
      <ReminderDialog
        open={reminderDialogOpen}
        actionTitle={action.title}
        onConfirm={handleReminder}
        onCancel={() => setReminderDialogOpen(false)}
      />
      <CouldNotCompleteDialog
        open={couldNotCompleteDialogOpen}
        actionTitle={action.title}
        onConfirm={handleCouldNotComplete}
        onCancel={() => setCouldNotCompleteDialogOpen(false)}
      />
    </>
  );
}
