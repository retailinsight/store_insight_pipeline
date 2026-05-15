import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

export interface ChatHistoryListItem {
  id: string;
  title: string;
  lastMessage: string;
  updatedAt: string;
}

interface ChatHistorySearchDialogProps {
  open: boolean;
  onClose: () => void;
  chats: ChatHistoryListItem[];
}

const formatChatTimestamp = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
};

export default function ChatHistorySearchDialog({
  open,
  onClose,
  chats,
}: ChatHistorySearchDialogProps) {
  const [query, setQuery] = useState("");

  const filteredChats = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return chats;

    return chats.filter((chat) => {
      const title = chat.title.toLowerCase();
      const preview = chat.lastMessage.toLowerCase();
      return title.includes(trimmed) || preview.includes(trimmed);
    });
  }, [chats, query]);

  const hasChats = chats.length > 0;
  const hasMatches = filteredChats.length > 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) {
          setQuery("");
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-xl rounded-2xl border-0 shadow-action p-6">
        <DialogHeader>
          <div className="flex items-center justify-center w-14 h-14 rounded-full bg-brand-primary-100 mx-auto mb-3">
            <Search size={24} className="text-brand-primary" />
          </div>
          <DialogTitle className="text-center font-dm-sans font-bold text-lg text-black">
            Search chats
          </DialogTitle>
          <DialogDescription className="text-center font-dm-sans text-sm text-brand-secondary-300 mt-2">
            Find previous conversations quickly.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-5">
          <Input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your chat history"
            className="h-11 rounded-xl border-app-neutral-400 bg-app-neutral-100 font-dm-sans text-sm focus-visible:ring-brand-primary/30 focus-visible:border-brand-primary"
          />
        </div>

        <div className="mt-4 rounded-xl border border-app-neutral-400 bg-white">
          <ScrollArea className="h-[320px] w-full sm:h-[360px]">
            <div className="p-2">
              {!hasChats && (
                <p className="py-20 text-center font-dm-sans text-sm text-brand-secondary-300">No chats yet</p>
              )}

              {hasChats && !hasMatches && (
                <p className="py-20 text-center font-dm-sans text-sm text-brand-secondary-300">No matching chats</p>
              )}

              {hasMatches &&
                filteredChats.map((chat) => (
                  <button
                    key={chat.id}
                    type="button"
                    className="w-full rounded-lg px-3 py-3 text-left transition-colors hover:bg-brand-primary-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary/30"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="line-clamp-1 font-dm-sans text-sm font-bold text-black">{chat.title}</p>
                      <p className="shrink-0 font-dm-sans text-xs text-brand-secondary-300">
                        {formatChatTimestamp(chat.updatedAt)}
                      </p>
                    </div>
                    <p className="mt-1 line-clamp-2 font-dm-sans text-sm text-brand-secondary-300">
                      {chat.lastMessage || "No messages yet"}
                    </p>
                  </button>
                ))}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}