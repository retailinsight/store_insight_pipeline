import { useState } from "react";

import ChatHistorySearchDialog, {
  type ChatHistoryListItem,
} from "@/components/dialogs/ChatHistorySearchDialog";
import Layout from "@/components/Layout";
import { useAppSelector } from "@/store/hooks";

const CHAT_HISTORY_STORAGE_KEYS = ["chatHistory", "chat_history"];

const normalizeChatHistory = (raw: unknown): ChatHistoryListItem[] => {
  if (!Array.isArray(raw)) return [];

  const normalized = raw.map((entry, index) => {
    const item = entry as Record<string, unknown>;

    const id = typeof item.id === "string" && item.id ? item.id : `chat-${index}`;
    const title =
      typeof item.title === "string" && item.title.trim()
        ? item.title.trim()
        : typeof item.name === "string" && item.name.trim()
          ? item.name.trim()
          : "Untitled chat";
    const lastMessage =
      typeof item.lastMessage === "string"
        ? item.lastMessage
        : typeof item.preview === "string"
          ? item.preview
          : typeof item.message === "string"
            ? item.message
            : "";
    const updatedAt =
      typeof item.updatedAt === "string"
        ? item.updatedAt
        : typeof item.timestamp === "string"
          ? item.timestamp
          : typeof item.createdAt === "string"
            ? item.createdAt
            : new Date(0).toISOString();

    return {
      id,
      title,
      lastMessage,
      updatedAt,
    };
  });

  return normalized.sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  );
};

const loadLocalChatHistory = (): ChatHistoryListItem[] => {
  if (typeof window === "undefined") return [];

  for (const key of CHAT_HISTORY_STORAGE_KEYS) {
    const value = window.localStorage.getItem(key);
    if (!value) continue;

    try {
      const parsed = JSON.parse(value) as unknown;

      if (
        parsed &&
        typeof parsed === "object" &&
        "chats" in parsed &&
        Array.isArray((parsed as { chats?: unknown }).chats)
      ) {
        return normalizeChatHistory((parsed as { chats: unknown[] }).chats);
      }

      return normalizeChatHistory(parsed);
    } catch {
      return [];
    }
  }

  return [];
};

function MicrophoneIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M24 16.0003C24 19.9577 21.112 23.2523 17.3333 23.8883V25.3337C17.3333 26.0697 16.7373 26.667 16 26.667C15.2627 26.667 14.6667 26.0697 14.6667 25.3337V23.8883C10.888 23.2523 8 19.9577 8 16.0003C8 15.2643 8.596 14.667 9.33333 14.667C10.0707 14.667 10.6667 15.2643 10.6667 16.0003C10.6667 18.9417 13.0587 21.3337 16 21.3337C18.9413 21.3337 21.3333 18.9417 21.3333 16.0003C21.3333 15.2643 21.9293 14.667 22.6667 14.667C23.404 14.667 24 15.2643 24 16.0003ZM13.3333 16.0003V9.33366C13.3333 7.86033 14.5267 6.66699 16 6.66699C17.4733 6.66699 18.6667 7.86033 18.6667 9.33366V16.0003C18.6667 17.4737 17.4733 18.667 16 18.667C14.5267 18.667 13.3333 17.4737 13.3333 16.0003Z" fill="#577DF7"/>
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <g clipPath="url(#clip0_chat_send)">
        <path d="M16 32C19.1645 32 22.2579 31.0616 24.8891 29.3035C27.5203 27.5454 29.5711 25.0466 30.7821 22.1229C31.9931 19.1993 32.3099 15.9823 31.6926 12.8786C31.0752 9.77487 29.5514 6.92394 27.3137 4.6863C25.0761 2.44866 22.2251 0.924806 19.1214 0.307443C16.0178 -0.309921 12.8007 0.00693258 9.87707 1.21793C6.95345 2.42894 4.45459 4.4797 2.69649 7.11088C0.938384 9.74207 0 12.8355 0 16C0.00458811 20.2421 1.69177 24.3091 4.69136 27.3087C7.69095 30.3082 11.7579 31.9954 16 32ZM14.1147 8.78134C14.6147 8.28142 15.2929 8.00058 16 8.00058C16.7071 8.00058 17.3853 8.28142 17.8853 8.78134L23.5427 14.4387L21.6573 16.324L17.3333 12V24H14.6667V12L10.3427 16.324L8.45733 14.4387L14.1147 8.78134Z" fill="#577DF7"/>
      </g>
      <defs>
        <clipPath id="clip0_chat_send">
          <rect width="32" height="32" fill="white"/>
        </clipPath>
      </defs>
    </svg>
  );
}

export default function Chat() {
  const user = useAppSelector((s) => s.auth.user);
  const [isSearchDialogOpen, setIsSearchDialogOpen] = useState(false);
  const [chatHistory] = useState<ChatHistoryListItem[]>(() => loadLocalChatHistory());
  const [chatInput, setChatInput] = useState("");

  const firstName = user?.username
    ? user.username.charAt(0).toUpperCase() + user.username.slice(1)
    : "there";

  return (
    <Layout>
      <div className="chat-page-wrapper">
        {/* Secondary AI sub-menu */}
        <aside className="chat-submenu">
          <div className="chat-submenu-inner">
            <button className="chat-submenu-btn" aria-label="New chat" style={{ backgroundColor: "#577DF7" }}>
              <img src="/new-chat.svg" alt="New chat" width={24} height={24} />
            </button>
            <button
              className="chat-submenu-btn"
              aria-label="Search chats"
              onClick={() => setIsSearchDialogOpen(true)}
            >
              <img src="/search.svg" alt="Search chats" width={32} height={32} />
            </button>
            <button className="chat-submenu-btn" aria-label="Recent chats">
              <img src="/chats.svg" alt="Recent chats" width={32} height={32} />
            </button>
          </div>
        </aside>

        {/* Main chat area */}
        <div className="chat-main">
          {/* Greeting area */}
          <div className="chat-greeting-area">
            <div className="chat-greeting-content">
              <div className="chat-greeting-header">
                <img src="/new-chat.svg" alt="New chat" width={42} height={36} />
                <h1 className="chat-greeting-title">Hello, {firstName}</h1>
              </div>

              {/* Chat input */}
              <div className="chat-input-card">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="How can I help you today?"
                  aria-label="Chat message"
                  className="chat-input-field"
                />
                <div className="chat-input-actions">
                  <button className="chat-action-btn" aria-label="Voice input">
                    <MicrophoneIcon />
                  </button>
                  <button className="chat-action-btn" aria-label="Send message">
                    <SendIcon />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Footer disclaimer */}
          <p className="chat-disclaimer">
            AI can make mistakes and may hallucinate. Always verify important information before acting on it.
          </p>
        </div>
      </div>

      <ChatHistorySearchDialog
        open={isSearchDialogOpen}
        onClose={() => setIsSearchDialogOpen(false)}
        chats={chatHistory}
      />
    </Layout>
  );
}
