import { useState } from "react";
import { MessageCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface FeedbackDialogProps {
  open: boolean;
  onSubmit: (feedback: string) => Promise<void>;
  onCancel: () => void;
}

export default function FeedbackDialog({
  open,
  onSubmit,
  onCancel,
}: FeedbackDialogProps) {
  const [feedback, setFeedback] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleClose = () => {
    setFeedback("");
    onCancel();
  };

  const handleSubmit = async () => {
    if (!feedback.trim()) return;
    setIsLoading(true);
    try {
      await onSubmit(feedback);
      setFeedback("");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md rounded-2xl border-0 shadow-action p-6">
        <DialogHeader>
          <div className="flex items-center justify-center w-14 h-14 rounded-full bg-blue-100 mx-auto mb-3">
            <MessageCircle size={28} className="text-blue-600" />
          </div>
          <DialogTitle className="text-center font-dm-sans font-bold text-lg">
            Send us your feedback
          </DialogTitle>
          <DialogDescription className="text-center font-dm-sans text-sm text-gray-600 mt-2">
            Help us improve by sharing your thoughts and suggestions.
          </DialogDescription>
        </DialogHeader>

        {/* Feedback textarea */}
        <div className="mt-5">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Share your feedback here..."
            className="w-full rounded-xl border border-app-neutral-400 bg-app-neutral-100 p-3 text-sm font-dm-sans resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary min-h-[120px]"
          />
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 mt-5">
          <button
            onClick={handleClose}
            className="flex-1 px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors disabled:opacity-50"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!feedback.trim() || isLoading}
            className="flex-1 px-4 py-2.5 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? "Submitting..." : "Submit feedback"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
