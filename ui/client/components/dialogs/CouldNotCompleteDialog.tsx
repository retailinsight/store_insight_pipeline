import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface CouldNotCompleteDialogProps {
  open: boolean;
  actionTitle: string;
  onConfirm: (reason: string, comment: string) => void;
  onCancel: () => void;
}

const REASONS = [
  "Supply issue - product not available",
  "Staffing - not enough resource",
  "HO dependency - waiting on head office",
  "Equipment issue",
  "Already resolved before action was generated",
  "Not applicable to this store",
  "Other",
];

export default function CouldNotCompleteDialog({
  open,
  actionTitle,
  onConfirm,
  onCancel,
}: CouldNotCompleteDialogProps) {
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!reason) return;
    onConfirm(reason, comment);
    setSubmitted(true);
  };

  const handleClose = () => {
    setSubmitted(false);
    setReason("");
    setComment("");
    onCancel();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md rounded-2xl border-0 shadow-action p-6">
        {!submitted ? (
          <>
            <DialogHeader>
              <DialogTitle className="font-dm-sans font-bold text-lg">
                Couldn't complete this action?
              </DialogTitle>
              <DialogDescription className="font-dm-sans text-sm text-gray-600 mt-1">
                Help us understand why{" "}
                <span className="font-semibold text-black">"{actionTitle}"</span>{" "}
                couldn't be completed. This helps us improve the relevance of future actions for your store.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-3 mt-4 max-h-[60vh] overflow-y-auto pr-1">
              <p className="font-dm-sans text-sm font-medium text-gray-800 sticky top-0 bg-white pb-2 z-10">
                Select a reason <span className="text-app-error">*</span>
              </p>

              <div className="flex flex-col gap-2 max-h-[30vh] overflow-y-auto pr-1">
                {REASONS.map((r) => (
                  <label
                    key={r}
                    className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                      reason === r
                        ? "border-brand-primary bg-brand-primary-100"
                        : "border-app-neutral-400 bg-app-neutral-100 hover:border-brand-primary/50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="reason"
                      value={r}
                      checked={reason === r}
                      onChange={() => setReason(r)}
                      className="accent-brand-primary"
                    />
                    <span className="font-dm-sans text-sm text-gray-800">{r}</span>
                  </label>
                ))}
              </div>

              <div className="flex flex-col gap-1.5 mt-1">
                <label className="font-dm-sans text-sm font-medium text-gray-600">
                  Additional comments (optional)
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="e.g. supplier out of stock, delivery delayed..."
                  className="w-full rounded-xl border border-app-neutral-400 bg-app-neutral-100 p-3 text-sm font-dm-sans resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary min-h-[80px]"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-4">
              <button
                onClick={handleClose}
                className="flex-1 px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!reason}
                className="flex-1 px-4 py-2.5 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Submit
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-4 py-4 text-center">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-brand-primary-100">
              <svg width="32" height="32" viewBox="0 0 32 37" fill="none">
                <path d="M31.5393 1.44756C30.9831 0.541102 30.0201 0 28.9656 0H24.3805C22.043 0 19.9478 1.31653 18.9147 3.43777L16.0789 9.25424C16.0469 9.25424 16.0149 9.24961 15.9829 9.24961C15.9616 9.24961 15.9418 9.2527 15.9205 9.2527L13.0847 3.43777C12.05 1.31653 9.95635 0 7.61886 0H3.03378C1.97932 0 1.01629 0.541102 0.458582 1.44756C-0.0976004 2.35403 -0.150933 3.46706 0.315346 4.4244L5.24023 14.5265C3.38578 16.8929 2.26884 19.8774 2.26884 23.1256C2.26884 30.775 8.4219 37 15.9829 37C23.544 37 29.697 30.775 29.697 23.1256C29.697 19.8898 28.5877 16.9175 26.7454 14.5543L31.684 4.42594C32.1518 3.46861 32.097 2.35557 31.5408 1.44911L31.5393 1.44756Z" fill="#577DF7"/>
              </svg>
            </div>
            <p className="font-dm-sans font-bold text-lg">Thank you for your feedback!</p>
            <p className="font-dm-sans text-sm text-gray-600 max-w-xs">
              Your response helps us continuously improve the quality of smart actions — not just for your store, but for every store in the network. Together we make the whole system smarter.
            </p>
            <button
              onClick={handleClose}
              className="mt-2 px-6 py-2.5 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity"
            >
              Done
            </button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
