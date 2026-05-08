import Layout from "@/components/Layout";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

function CartIcon() {
  return (
    <svg width="42" height="36" viewBox="0 0 42 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <g clipPath="url(#clip0_chat_cart)">
        <path d="M1.19922 1.19922H6.59922L10.1992 21.5992H32.9992L37.1992 7.19922H13.1992" stroke="#577DF7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M14.3994 31.8008C16.0563 31.8008 17.3994 30.4576 17.3994 28.8008C17.3994 27.1439 16.0563 25.8008 14.3994 25.8008C12.7426 25.8008 11.3994 27.1439 11.3994 28.8008C11.3994 30.4576 12.7426 31.8008 14.3994 31.8008Z" fill="#577DF7"/>
        <path d="M28.8008 31.8008C30.4576 31.8008 31.8008 30.4576 31.8008 28.8008C31.8008 27.1439 30.4576 25.8008 28.8008 25.8008C27.1439 25.8008 25.8008 27.1439 25.8008 28.8008C25.8008 30.4576 27.1439 31.8008 28.8008 31.8008Z" fill="#577DF7"/>
      </g>
      <defs>
        <clipPath id="clip0_chat_cart">
          <rect width="42" height="36" fill="white"/>
        </clipPath>
      </defs>
    </svg>
  );
}

function NewChatIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" rx="12" fill="#577DF7"/>
      <path fillRule="evenodd" clipRule="evenodd" d="M17.4684 6.53214C16.7582 5.82262 15.6069 5.82262 14.8966 6.53214L6.735 14.6939C6.26327 15.1634 5.9985 15.8024 6.00001 16.4677V17.4982C6.00001 17.7757 6.22427 18 6.50177 18H7.5323C8.19753 18.0022 8.83653 17.7375 9.30607 17.2657L17.4684 9.10322C18.1772 8.39295 18.1772 7.24242 17.4684 6.53214ZM8.59657 16.5562C8.31303 16.8367 7.93056 16.9949 7.5323 16.9964H7.00353V16.4677C7.00279 16.0687 7.16104 15.6854 7.44454 15.4034L13.6389 9.20971L14.7931 10.3632L8.59657 16.5562ZM16.7582 8.3937L15.5004 9.65148L14.3461 8.49945L15.6047 7.24166C15.9234 6.92365 16.4394 6.92441 16.7574 7.24316C17.0754 7.56192 17.0747 8.07794 16.7559 8.39595L16.7582 8.3937Z" fill="white"/>
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path fillRule="evenodd" clipRule="evenodd" d="M17.8125 16.8709L13.8366 12.8949C16.1695 10.0429 15.7475 5.83887 12.8956 3.50687C10.0426 1.17487 5.83958 1.59587 3.50657 4.44887C1.17454 7.30088 1.59654 11.5049 4.4486 13.8369C6.90556 15.8459 10.4375 15.8459 12.8956 13.8369L16.8716 17.8129C17.1355 18.0689 17.5575 18.0609 17.8125 17.7969C18.0625 17.5379 18.0625 17.1289 17.8125 16.8709ZM8.68254 14.0109C5.73955 14.0109 3.35356 11.6259 3.35356 8.68288C3.35356 5.73987 5.73955 3.35387 8.68254 3.35387C11.6256 3.35387 14.0116 5.73987 14.0116 8.68288C14.0086 11.6239 11.6246 14.0079 8.68254 14.0109Z" fill="#737188"/>
    </svg>
  );
}

function RecentChatsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M14.9808 8.0619C15.135 5.87856 14.3383 3.74106 12.7958 2.19856C11.2533 0.656062 9.12333 -0.128938 6.95667 0.0185624C3.18583 0.286062 0 3.83106 0 7.76023V12.0836C0 13.9919 1.00833 15.0002 2.91667 15.0002H7.2375C11.1692 15.0002 14.7158 11.8236 14.9808 8.0619ZM7.2375 14.1669H2.91667C1.47583 14.1669 0.833333 13.5244 0.833333 12.0836V7.76023C0.833333 4.08356 3.9325 0.800229 7.48667 0.833562C11.255 0.751062 14.4992 4.24356 14.1492 8.00356C13.9133 11.3452 10.7483 14.1669 7.2375 14.1669ZM20 13.5627V17.5011C20 19.0427 19.0425 20.0002 17.5 20.0002H13.565C11.3167 20.0002 9.10333 18.8136 7.78833 16.9027C7.65833 16.7127 7.70583 16.4536 7.89583 16.3236C8.08583 16.1936 8.345 16.2402 8.475 16.4311C9.63583 18.1186 11.5858 19.1669 13.5642 19.1669H17.4992C18.26 19.1669 19.1658 18.8777 19.1658 17.5011V13.5627C19.1658 11.5844 18.1175 9.63523 16.43 8.47523C16.24 8.34523 16.1925 8.08523 16.3225 7.89606C16.4542 7.7069 16.7125 7.65856 16.9017 7.78856C18.8117 9.1019 19.9992 11.3144 19.9992 13.5636L20 13.5627ZM8.33333 7.50023C8.33333 7.96023 7.96 8.33356 7.5 8.33356C7.04 8.33356 6.66667 7.96023 6.66667 7.50023C6.66667 7.04023 7.04 6.6669 7.5 6.6669C7.96 6.6669 8.33333 7.04023 8.33333 7.50023ZM5 7.50023C5 7.96023 4.62667 8.33356 4.16667 8.33356C3.70667 8.33356 3.33333 7.96023 3.33333 7.50023C3.33333 7.04023 3.70667 6.6669 4.16667 6.6669C4.62667 6.6669 5 7.04023 5 7.50023ZM11.6667 7.50023C11.6667 7.96023 11.2933 8.33356 10.8333 8.33356C10.3733 8.33356 10 7.96023 10 7.50023C10 7.04023 10.3733 6.6669 10.8333 6.6669C11.2933 6.6669 11.6667 7.04023 11.6667 7.50023Z" fill="#737188"/>
    </svg>
  );
}

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
  const { user } = useAuth();
  const firstName = user?.username
    ? user.username.charAt(0).toUpperCase() + user.username.slice(1)
    : "there";

  return (
    <Layout>
      <div className="chat-page-wrapper">
        {/* Secondary AI sub-menu */}
        <aside className="chat-submenu">
          <div className="chat-submenu-inner">
            <button className="chat-submenu-btn" aria-label="New chat">
              <NewChatIcon />
            </button>
            <button className="chat-submenu-btn chat-submenu-btn--bordered" aria-label="Search chats">
              <SearchIcon />
            </button>
            <button className="chat-submenu-btn" aria-label="Recent chats">
              <RecentChatsIcon />
            </button>
          </div>
        </aside>

        {/* Main chat area */}
        <div className="chat-main">
          {/* Greeting area */}
          <div className="chat-greeting-area">
            <div className="chat-greeting-content">
              <div className="chat-greeting-header">
                <CartIcon />
                <h1 className="chat-greeting-title">Hello, {firstName}</h1>
              </div>

              {/* Chat input */}
              <div className="chat-input-card">
                <p className="chat-input-placeholder">How can I help you today?</p>
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
    </Layout>
  );
}
