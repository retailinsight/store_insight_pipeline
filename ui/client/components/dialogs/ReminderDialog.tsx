import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface ReminderDialogProps {
  open: boolean;
  actionTitle: string;
  onConfirm: (date: string, time: string, method: string) => void;
  onCancel: () => void;
}

export default function ReminderDialog({
  open,
  actionTitle,
  onConfirm,
  onCancel,
}: ReminderDialogProps) {
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [method, setMethod] = useState("in-app-push");
  const [confirmed, setConfirmed] = useState(false);

  const today = new Date().toISOString().split("T")[0];

  const handleSubmit = () => {
    if (!date || !time) return;
    onConfirm(date, time, method);
    setConfirmed(true);
    setTimeout(() => {
      setConfirmed(false);
      setDate("");
      setTime("");
      setMethod("in-app-push");
    }, 300);
  };

  const handleClose = () => {
    setConfirmed(false);
    setDate("");
    setTime("");
    setMethod("in-app-push");
    onCancel();
  };

  const deliveryMethods = [
    { value: "in-app-push", label: "In-app & Push notification" },
    { value: "in-app", label: "In-app only" },
    { value: "email", label: "Email" },
    { value: "teams", label: "Microsoft Teams" },
    { value: "slack", label: "Slack" },
  ];

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md rounded-2xl border-0 shadow-action p-6">
        {!confirmed ? (
          <>
            <DialogHeader>
              <div className="flex items-center justify-center w-14 h-14 rounded-full bg-brand-primary-100 mx-auto mb-3">
                <svg width="26" height="26" viewBox="0 0 20 20" fill="none">
                  <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674Z" fill="#577DF7"/>
                </svg>
              </div>
              <DialogTitle className="text-center font-dm-sans font-bold text-lg">
                Set a Reminder
              </DialogTitle>
              <DialogDescription className="text-center font-dm-sans text-sm text-gray-600">
                Schedule a reminder for{" "}
                <span className="font-semibold text-black">"{actionTitle}"</span>
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-4 mt-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="font-dm-sans text-xs font-medium text-gray-600">Date</label>
                  <input
                    type="date"
                    min={today}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="rounded-xl border border-app-neutral-400 bg-app-neutral-100 px-3 py-2.5 text-sm font-dm-sans focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="font-dm-sans text-xs font-medium text-gray-600">Time</label>
                  <input
                    type="time"
                    value={time}
                    onChange={(e) => setTime(e.target.value)}
                    className="rounded-xl border border-app-neutral-400 bg-app-neutral-100 px-3 py-2.5 text-sm font-dm-sans focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="font-dm-sans text-xs font-medium text-gray-600">
                  Delivery method
                </label>
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                  className="rounded-xl border border-app-neutral-400 bg-app-neutral-100 px-3 py-2.5 text-sm font-dm-sans focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary appearance-none cursor-pointer"
                >
                  {deliveryMethods.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-3 mt-5">
              <button
                onClick={handleClose}
                className="flex-1 px-4 py-2.5 rounded-full border border-brand-outline-border text-brand-outline-text text-sm font-dm-sans hover:bg-brand-primary-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!date || !time}
                className="flex-1 px-4 py-2.5 rounded-full bg-brand-primary text-white text-sm font-dm-sans hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Set reminder
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-app-lime">
              <svg width="32" height="32" viewBox="0 0 20 20" fill="none">
                <path d="M16.8609 4.19619L7.64819 13.4082C7.58625 13.4704 7.51264 13.5197 7.43159 13.5534C7.35053 13.5871 7.26363 13.6044 7.17586 13.6044C7.08809 13.6044 7.00118 13.5871 6.92013 13.5534C6.83908 13.5197 6.76547 13.4704 6.70353 13.4082L3.14086 9.84219C3.07892 9.78001 3.00531 9.73067 2.92426 9.697C2.8432 9.66333 2.7563 9.646 2.66853 9.646C2.58076 9.646 2.49385 9.66333 2.4128 9.697C2.33174 9.73067 2.25813 9.78001 2.19619 9.84219C2.13401 9.90413 2.08467 9.97774 2.051 10.0588C2.01733 10.1399 2 10.2268 2 10.3145C2 10.4023 2.01733 10.4892 2.051 10.5703C2.08467 10.6513 2.13401 10.7249 2.19619 10.7869L5.76019 14.3502C6.13616 14.7255 6.64566 14.9362 7.17686 14.9362C7.70806 14.9362 8.21756 14.7255 8.59353 14.3502L17.8055 5.14019C17.9169 5.0047 17.9505 4.9237 17.9841 4.84271C18.0014 4.75588 18.0014 4.66819 18.0014 4.66819C18.0014 4.5805 17.9841 4.49367 17.9505 4.41268C17.9169 4.33169 17.8676 4.25812 17.8055 4.19619C17.7436 4.13401 17.67 4.08467 17.5889 4.051C17.5079 4.01733 17.421 4 17.3332 4C17.2454 4 17.1585 4.01733 17.0775 4.051C16.9964 4.08467 16.9228 4.13401 16.8609 4.19619Z" fill="#000"/>
              </svg>
            </div>
            <p className="font-dm-sans font-bold text-lg text-center">Reminder set!</p>
            <p className="font-dm-sans text-sm text-gray-600 text-center">
              We'll remind you on <strong>{date}</strong> at <strong>{time}</strong> via{" "}
              {deliveryMethods.find((m) => m.value === method)?.label}.
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
