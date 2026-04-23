import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface CompleteActionDialogProps {
  open: boolean;
  actionTitle: string;
  onConfirm: (opinion: "positive" | "negative", feedback: string) => void;
  onCancel: () => void;
}

export default function CompleteActionDialog({
  open,
  actionTitle,
  onConfirm,
  onCancel,
}: CompleteActionDialogProps) {
  const [opinion, setOpinion] = useState<"positive" | "negative" | null>(null);
  const [feedback, setFeedback] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleClose = () => {
    setOpinion(null);
    setFeedback("");
    onCancel();
  };

  const handleSubmit = async () => {
    if (!opinion) return;
    setIsLoading(true);
    try {
      await onConfirm(opinion, feedback);
    } finally {
      setIsLoading(false);
      setOpinion(null);
      setFeedback("");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md rounded-2xl border-0 shadow-action p-6">
        <DialogHeader>
          <div className="flex items-center justify-center w-14 h-14 rounded-full bg-brand-primary-100 mx-auto mb-3">
            <svg width="28" height="28" viewBox="0 0 20 20" fill="none">
              <path d="M16.8609 4.19619L7.64819 13.4082C7.58625 13.4704 7.51264 13.5197 7.43159 13.5534C7.35053 13.5871 7.26363 13.6044 7.17586 13.6044C7.08809 13.6044 7.00118 13.5871 6.92013 13.5534C6.83908 13.5197 6.76547 13.4704 6.70353 13.4082L3.14086 9.84219C3.07892 9.78001 3.00531 9.73067 2.92426 9.697C2.8432 9.66333 2.7563 9.646 2.66853 9.646C2.58076 9.646 2.49385 9.66333 2.4128 9.697C2.33174 9.73067 2.25813 9.78001 2.19619 9.84219C2.13401 9.90413 2.08467 9.97774 2.051 10.0588C2.01733 10.1399 2 10.2268 2 10.3145C2 10.4023 2.01733 10.4892 2.051 10.5703C2.08467 10.6513 2.13401 10.7249 2.19619 10.7869L5.76019 14.3502C6.13616 14.7255 6.64566 14.9362 7.17686 14.9362C7.70806 14.9362 8.21756 14.7255 8.59353 14.3502L17.8055 5.14019C17.8676 5.07827 17.9169 5.0047 17.9505 4.9237C17.9841 4.84271 18.0014 4.75588 18.0014 4.66819C18.0014 4.5805 17.9841 4.49367 17.9505 4.41268C17.9169 4.33169 17.8676 4.25812 17.8055 4.19619C17.7436 4.13401 17.67 4.08467 17.5889 4.051C17.5079 4.01733 17.421 4 17.3332 4C17.2454 4 17.1585 4.01733 17.0775 4.051C16.9964 4.08467 16.9228 4.13401 16.8609 4.19619Z" fill="#577DF7"/>
            </svg>
          </div>
          <DialogTitle className="text-center font-dm-sans font-bold text-lg">
            Mark this action as complete?
          </DialogTitle>
          <DialogDescription className="text-center font-dm-sans text-sm text-gray-600 mt-3">
            Before you go - what did you think of the action? Your feedback will help us ensure the quality of the actions we send you.
          </DialogDescription>
        </DialogHeader>

        {/* Opinion selection */}
        <div className="flex gap-4 justify-center mt-5">
          <button
            onClick={() => setOpinion("positive")}
            className={`flex items-center justify-center w-12 h-12 rounded-full transition-all ${
              opinion === "positive"
                ? "bg-green-100 text-green-600"
                : "bg-gray-100 text-gray-400 hover:bg-gray-200"
            }`}
            title="Positive feedback"
          >
            <ThumbsUp size={24} />
          </button>
          <button
            onClick={() => setOpinion("negative")}
            className={`flex items-center justify-center w-12 h-12 rounded-full transition-all ${
              opinion === "negative"
                ? "bg-red-100 text-red-600"
                : "bg-gray-100 text-gray-400 hover:bg-gray-200"
            }`}
            title="Negative feedback"
          >
            <ThumbsDown size={24} />
          </button>
        </div>

        {/* Feedback textarea */}
        <div className="mt-5">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Optional. Share how useful you found the action or any suggestions on how to improve it."
            className="w-full rounded-xl border border-app-neutral-400 bg-app-neutral-100 p-3 text-sm font-dm-sans resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary min-h-[80px]"
          />
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 mt-5">
          <button
            onClick={handleClose}
            className="flex-1 px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!opinion || isLoading}
            className="flex-1 px-4 py-2.5 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? "Completing..." : "Yes, complete"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
