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
  onClose: () => void;
}

export default function FeedbackDialog({ open, onClose }: FeedbackDialogProps) {
  const [feedback, setFeedback] = useState("");

  const handleClose = () => {
    setFeedback("");
    onClose();
  };

  const handleSubmit = () => {
    // TODO: wire up to API when ready
    handleClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md rounded-2xl border-0 shadow-action p-6">
        <DialogHeader>
          <div className="flex items-center justify-center w-14 h-14 rounded-full bg-brand-primary-100 mx-auto mb-3">
            <MessageCircle size={28} className="text-brand-primary" />
          </div>
          <DialogTitle className="text-center font-dm-sans font-bold text-lg">
            Send us your feedback
          </DialogTitle>
          <DialogDescription className="text-center font-dm-sans text-sm text-gray-600 mt-1">
            Help us improve by sharing your thoughts and suggestions.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          <textarea
            className="w-full h-32 px-4 py-3 rounded-xl border border-gray-200 font-dm-sans text-sm text-black placeholder:text-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary transition-colors"
            placeholder="Share your feedback here..."
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </div>

        <div className="flex gap-3 mt-4">
          <button
            onClick={handleClose}
            className="flex-1 px-4 py-3 rounded-full border border-gray-200 font-dm-sans text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!feedback.trim()}
            className="flex-1 px-4 py-3 rounded-full bg-brand-primary font-dm-sans text-sm text-white hover:bg-brand-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Submit feedback
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
