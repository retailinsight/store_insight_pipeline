import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { CheckBoldIcon } from "@/components/icons";

interface CompleteActionDialogProps {
  open: boolean;
  actionTitle: string;
  onConfirm: (feedback: string) => void;
  onCancel: () => void;
}

export default function CompleteActionDialog({
  open,
  actionTitle,
  onConfirm,
  onCancel,
}: CompleteActionDialogProps) {
  const [step, setStep] = useState<"confirm" | "feedback" | "success">("confirm");
  const [feedback, setFeedback] = useState("");

  const handleConfirm = () => {
    setStep("feedback");
  };

  const handleSubmit = () => {
    onConfirm(feedback);
    setStep("success");
    setTimeout(() => {
      setStep("confirm");
      setFeedback("");
    }, 300);
  };

  const handleClose = () => {
    setStep("confirm");
    setFeedback("");
    onCancel();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md rounded-2xl border-0 shadow-action p-6">
        {step === "confirm" && (
          <>
            <DialogHeader>
              <div className="flex items-center justify-center w-14 h-14 rounded-full bg-brand-primary-100 mx-auto mb-3">
                <CheckBoldIcon size={28} className="text-brand-primary" />
              </div>
              <DialogTitle className="text-center font-dm-sans font-bold text-lg">
                Mark as Complete?
              </DialogTitle>
              <DialogDescription className="text-center font-dm-sans text-sm text-gray-600 mt-2">
                Are you sure you want to mark <span className="font-semibold text-black">"{actionTitle}"</span> as complete?
                This action will be logged with your name and timestamp.
              </DialogDescription>
            </DialogHeader>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleClose}
                className="flex-1 px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                className="flex-1 px-4 py-2.5 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity"
              >
                Yes, complete
              </button>
            </div>
          </>
        )}

        {step === "feedback" && (
          <>
            <DialogHeader>
              <DialogTitle className="font-dm-sans font-bold text-lg">
                Great work!
              </DialogTitle>
              <DialogDescription className="font-dm-sans text-sm text-gray-600 mt-1">
                Your action has been logged. Would you like to share any feedback? Your insights help improve the quality of future smart actions for all stores.
              </DialogDescription>
            </DialogHeader>
            <div className="mt-4">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Optional: Share what worked, any challenges, or tips for others..."
                className="w-full rounded-xl border border-app-neutral-400 bg-app-neutral-100 p-3 text-sm font-dm-sans resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary min-h-[100px]"
              />
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => handleSubmit()}
                className="px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors"
              >
                Skip
              </button>
              <button
                onClick={handleSubmit}
                className="flex-1 px-4 py-2.5 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity"
              >
                Submit feedback
              </button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
