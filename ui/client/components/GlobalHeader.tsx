import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function formatDateTime(date: Date) {
  const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const day = dayNames[date.getDay()];
  const d = date.getDate();
  const month = monthNames[date.getMonth()];
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return { date: `${day}, ${d} ${month} ${year}`, time: `${hours}:${minutes}` };
}

export default function GlobalHeader() {
  const { selectedStore, canSwitchStores, availableStores, selectStore } = useAuth();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="h-16 border-b border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 px-6 flex items-center justify-between shrink-0">
      {/* Left side: Store info */}
      <div className="flex items-center gap-4">
        <span className="font-bebas text-lg text-black dark:text-white tracking-wide">
          Store {selectedStore?.id}: {selectedStore?.name}
        </span>
      </div>

      {/* Right side: Date/time and store selector */}
      <div className="flex items-center gap-6">
        {/* Date/time */}
        <div className="flex items-center gap-2 text-black/50 dark:text-white/50">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
            <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674ZM12.3343 12.0001C12.3343 11.4475 12.7816 11.0002 13.3342 11.0002C13.8859 11.0002 14.3341 11.4475 14.3341 12.0001C14.3341 12.5518 13.8859 13 13.3342 13C12.7816 13 12.3343 12.5518 12.3343 12.0001ZM9.00051 12.0001C9.00051 11.4475 9.44783 11.0002 10.0005 11.0002C10.5531 11.0002 11.0004 11.4475 11.0004 12.0001C11.0004 12.5518 10.5531 13 10.0005 13C9.44783 13 9.00051 12.5518 9.00051 12.0001ZM5.66676 12.0001C5.66676 11.4475 6.11498 11.0002 6.6667 11.0002C7.21933 11.0002 7.66665 11.4475 7.66665 12.0001C7.66665 12.5518 7.21933 13 6.6667 13C6.11498 13 5.66676 12.5518 5.66676 12.0001Z" fill="currentColor"/>
          </svg>
          <span className="font-dm-sans text-sm whitespace-nowrap">
            {formatDateTime(now).date} &bull; {formatDateTime(now).time}
          </span>
        </div>

        {/* Store selector for cluster leads */}
        {canSwitchStores && availableStores.length > 0 && (
          <Select 
            value={String(selectedStore?.id || "")}
            onValueChange={(storeId) => {
              const selected = availableStores.find(s => String(s.id) === storeId);
              if (selected) {
                selectStore(selected);
              }
            }}
          >
            <SelectTrigger className="w-[250px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {availableStores.map((store) => (
                <SelectItem key={store.id} value={String(store.id)}>
                  Store {store.id}: {store.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  );
}
