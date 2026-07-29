import { useState, useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { selectStore as selectStoreAction } from "@/store/slices/authSlice";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDateTime } from "@/lib/formatting";
import { CalendarDotsIcon } from "@/components/icons";

export default function GlobalHeader() {
  const dispatch = useAppDispatch();
  const selectedStore = useAppSelector((s) => s.auth.selectedStore);
  const availableStores = useAppSelector((s) => s.auth.availableStores);
  const canSwitchStores = useAppSelector((s) => s.auth.user?.roleId === 2);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="h-16 border-b border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 px-6 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-4">
        <span className="font-bebas text-lg text-black dark:text-white tracking-wide">
          Store {selectedStore?.id}: {selectedStore?.name}
        </span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 text-black/50 dark:text-white/50">
          <CalendarDotsIcon size={16} className="shrink-0" />
          <span className="font-dm-sans text-sm whitespace-nowrap">
            {formatDateTime(now).date} &bull; {formatDateTime(now).time}
          </span>
        </div>

        {canSwitchStores && availableStores.length > 0 && (
          <Select
            value={String(selectedStore?.id || "")}
            onValueChange={(storeId) => {
              const selected = availableStores.find(
                (s) => String(s.id) === storeId,
              );
              if (selected) {
                dispatch(selectStoreAction(selected));
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
