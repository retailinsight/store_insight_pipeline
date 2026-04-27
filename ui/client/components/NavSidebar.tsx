import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useSmartActions } from "@/contexts/SmartActionsContext";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";

interface NavItem {
  path: string;
  label: string;
  badge?: number;
  icon: React.ReactNode;
  hidden?: boolean; // Set to true to hide the item without deleting it
}

function DashboardIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <path d="M2.66667 14.6667H17.3333C18.0406 14.6667 18.7189 14.3857 19.219 13.8856C19.719 13.3855 20 12.7072 20 12V2.66667C20 1.95942 19.719 1.28115 19.219 0.781049C18.7189 0.280952 18.0406 0 17.3333 0L2.66667 0C1.95942 0 1.28115 0.280952 0.781049 0.781049C0.280952 1.28115 0 1.95942 0 2.66667L0 12C0 12.7072 0.280952 13.3855 0.781049 13.8856C1.28115 14.3857 1.95942 14.6667 2.66667 14.6667ZM2.66667 2.66667H17.3333V12H2.66667V2.66667Z" fill="currentColor"/>
      <path d="M29.3332 0H25.3332C24.6259 0 23.9477 0.280952 23.4476 0.781049C22.9475 1.28115 22.6665 1.95942 22.6665 2.66667V12C22.6665 12.7072 22.9475 13.3855 23.4476 13.8856C23.9477 14.3857 24.6259 14.6667 25.3332 14.6667H29.3332C30.0404 14.6667 30.7187 14.3857 31.2188 13.8856C31.7189 13.3855 31.9998 12.7072 31.9998 12V2.66667C31.9998 1.95942 31.7189 1.28115 31.2188 0.781049C30.7187 0.280952 30.0404 0 29.3332 0ZM29.3332 12H25.3332V2.66667H29.3332V12Z" fill="currentColor"/>
      <path d="M6.66667 17.3333H2.66667C1.95942 17.3333 1.28115 17.6142 0.781049 18.1143C0.280952 18.6144 0 19.2927 0 19.9999L0 29.3333C0 30.0405 0.280952 30.7188 0.781049 31.2189C1.28115 31.719 1.95942 31.9999 2.66667 31.9999H6.66667C7.37391 31.9999 8.05219 31.719 8.55229 31.2189C9.05238 30.7188 9.33333 30.0405 9.33333 29.3333V19.9999C9.33333 19.2927 9.05238 18.6144 8.55229 18.1143C8.05219 17.6142 7.37391 17.3333 6.66667 17.3333ZM6.66667 29.3333H2.66667V19.9999H6.66667V29.3333Z" fill="currentColor"/>
      <path d="M29.3333 17.3333H14.6667C13.9594 17.3333 13.2811 17.6142 12.781 18.1143C12.281 18.6144 12 19.2927 12 19.9999V29.3333C12 30.0405 12.281 30.7188 12.781 31.2189C13.2811 31.719 13.9594 31.9999 14.6667 31.9999H29.3333C30.0406 31.9999 30.7189 31.719 31.219 31.2189C31.719 30.7188 32 30.0405 32 29.3333V19.9999C32 19.2927 31.719 18.6144 31.219 18.1143C30.7189 17.6142 30.0406 17.3333 29.3333 17.3333ZM29.3333 29.3333H14.6667V19.9999H29.3333V29.3333Z" fill="currentColor"/>
    </svg>
  );
}

function SmartActionsIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <path d="M16.7548 32H11.6254L14.2921 21.3333H8.78142C8.24885 21.3331 7.72372 21.2083 7.24799 20.9689C6.77225 20.7296 6.3591 20.3822 6.04156 19.9547C5.72401 19.5271 5.51087 19.0313 5.41917 18.5066C5.32746 17.982 5.35974 17.4432 5.51342 16.9333L10.6348 0H23.2574L19.2574 10.6667H24.6214C25.2317 10.6671 25.8305 10.8328 26.3541 11.1463C26.8777 11.4598 27.3066 11.9093 27.5952 12.4471C27.8838 12.9848 28.0212 13.5907 27.993 14.2003C27.9647 14.81 27.7718 15.4006 27.4348 15.9093L16.7548 32ZM15.0414 29.3333H15.3241L25.2121 14.4347C25.2829 14.3278 25.3235 14.2038 25.3295 14.0757C25.3354 13.9477 25.3066 13.8204 25.246 13.7074C25.1854 13.5944 25.0954 13.5 24.9854 13.4341C24.8754 13.3683 24.7496 13.3334 24.6214 13.3333H15.4094L19.4094 2.66667H12.6134L8.06542 17.7013C8.03147 17.8131 8.02418 17.9313 8.04414 18.0465C8.06411 18.1616 8.11076 18.2704 8.18037 18.3643C8.24997 18.4581 8.3406 18.5344 8.44497 18.5869C8.54935 18.6394 8.66458 18.6667 8.78142 18.6667H17.7148L15.0414 29.3333Z" fill="currentColor"/>
    </svg>
  );
}

function MedalIcon() {
  return (
    <svg width="26" height="30" viewBox="0 0 32 37" fill="none">
      <path d="M31.5393 1.44756C30.9831 0.541102 30.0201 0 28.9656 0H24.3805C22.043 0 19.9478 1.31653 18.9147 3.43777L16.0789 9.25424C16.0469 9.25424 16.0149 9.24961 15.9829 9.24961C15.9616 9.24961 15.9418 9.2527 15.9205 9.2527L13.0847 3.43777C12.05 1.31653 9.95635 0 7.61886 0H3.03378C1.97932 0 1.01629 0.541102 0.458582 1.44756C-0.0976004 2.35403 -0.150933 3.46706 0.315346 4.4244L5.24023 14.5265C3.38578 16.8929 2.26884 19.8774 2.26884 23.1256C2.26884 30.775 8.4219 37 15.9829 37C23.544 37 29.697 30.775 29.697 23.1256C29.697 19.8898 28.5877 16.9175 26.7454 14.5543L31.684 4.42594C32.1518 3.46861 32.097 2.35557 31.5408 1.44911L31.5393 1.44756ZM7.61734 3.0832C8.78608 3.0832 9.83292 3.74147 10.3495 4.80209L12.719 9.66276C10.7929 10.1407 9.02531 11.0255 7.51372 12.2311L3.03226 3.0832H7.61734ZM15.9814 33.9153C10.0996 33.9153 5.31489 29.0746 5.31489 23.124C5.31489 17.4818 9.61959 12.8446 15.0808 12.3791C15.0824 12.3791 15.0839 12.3791 15.0869 12.3791C15.3826 12.3544 15.6812 12.3328 15.9829 12.3328C21.8647 12.3328 26.6494 17.1735 26.6494 23.124C26.6494 29.0746 21.8647 33.9153 15.9829 33.9153H15.9814ZM24.4689 12.248C22.9604 11.0394 21.1958 10.153 19.2728 9.67047L21.6468 4.80209C22.1634 3.74147 23.2103 3.0832 24.379 3.0832L28.9504 3.06008L24.4689 12.248Z" fill="currentColor"/>
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
      <path d="M27.5511 12.9834L23.4135 8.84582C23.2124 8.65152 22.9429 8.544 22.6632 8.54643C22.3836 8.54886 22.116 8.66104 21.9183 8.85881C21.7205 9.05658 21.6083 9.32411 21.6059 9.60379C21.6034 9.88347 21.711 10.1529 21.9053 10.3541L26.0429 14.4917C26.1658 14.617 26.2732 14.7567 26.3629 14.9077C26.3469 14.9077 26.3341 14.8992 26.3181 14.8992L9.58846 14.9333C9.30556 14.9333 9.03425 15.0457 8.83421 15.2457C8.63418 15.4457 8.52179 15.7171 8.52179 16C8.52179 16.2828 8.63418 16.5542 8.83421 16.7542C9.03425 16.9542 9.30556 17.0666 9.58846 17.0666L26.3117 17.0325C26.3415 17.0325 26.3661 17.0176 26.3949 17.0154C26.3002 17.1959 26.1803 17.3618 26.0386 17.5082L21.901 21.6458C21.7068 21.8419 21.5985 22.1072 21.5998 22.3834C21.6011 22.6596 21.7119 22.9238 21.9079 23.118C22.104 23.3122 22.3693 23.4198 22.6455 23.4184C22.9217 23.417 23.1859 23.3065 23.3801 23.1105L27.5177 18.973C28.3175 18.1729 28.7669 17.0878 28.7669 15.9564C28.7669 14.825 28.3175 13.7399 27.5177 12.9398L27.5511 12.9834Z" fill="currentColor"/>
      <path d="M10.6669 26.6666H8.53353C7.68484 26.6666 6.8709 26.3295 6.27079 25.7294C5.67067 25.1292 5.33353 24.3153 5.33353 23.4666V8.53328C5.33353 7.68459 5.67067 6.87066 6.27079 6.27054C6.8709 5.67043 7.68484 5.33328 8.53353 5.33328H10.6669C10.9498 5.33328 11.2211 5.2209 11.4211 5.02087C11.6211 4.82083 11.7335 4.54952 11.7335 4.26662C11.7335 3.98372 11.6211 3.71241 11.4211 3.51237C11.2211 3.31233 10.9498 3.19995 10.6669 3.19995H8.53353C7.11956 3.20164 5.76399 3.76409 4.76416 4.76392C3.76434 5.76375 3.20189 7.11932 3.2002 8.53328L3.2002 23.4666C3.20189 24.8806 3.76434 26.2362 4.76416 27.236C5.76399 28.2358 7.11956 28.7983 8.53353 28.8H10.6669C10.9498 28.8 11.2211 28.6876 11.4211 28.4875C11.6211 28.2875 11.7335 28.0162 11.7335 27.7333C11.7335 27.4504 11.6211 27.1791 11.4211 26.979C11.2211 26.779 10.9498 26.6666 10.6669 26.6666Z" fill="currentColor"/>
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4"/>
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  );
}

function HamburgerIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="6" x2="21" y2="6"/>
      <line x1="3" y1="12" x2="21" y2="12"/>
      <line x1="3" y1="18" x2="21" y2="18"/>
    </svg>
  );
}

interface NavSidebarProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  /** On mobile this controls the overlay open state; passed from Layout */
  mobileOpen: boolean;
  onToggleMobile: () => void;
  /** On desktop this controls the expanded overlay state; passed from Layout */
  desktopOpen: boolean;
  onToggleDesktop: () => void;
}

export default function NavSidebar({ darkMode, onToggleDarkMode, mobileOpen, onToggleMobile, desktopOpen, onToggleDesktop }: NavSidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { getVisibleActions, getActionsByStatus } = useSmartActions();
  const { logout } = useAuth();
  const { toast } = useToast();

  const handleLogout = () => {
    // Show success message before logging out and navigating
    toast({
      title: "Successfully logged out",
      description: "See you next time!",
    });
    // Logout without showing the message (we're showing it above)
    logout(false);
    // Navigate after a small delay to ensure toast is visible
    setTimeout(() => {
      navigate("/login");
    }, 300);
  };

  const pendingAndReminderCount = getVisibleActions().length;
  const completedSuccessesCount = getActionsByStatus("completed").length;

  const navItems: NavItem[] = [
    { path: "/", label: "Dashboard", icon: <DashboardIcon /> },
    { path: "/smart-actions", label: "Smart Actions", badge: pendingAndReminderCount, icon: <SmartActionsIcon /> },
    { path: "/successes", label: "Successes", badge: completedSuccessesCount, icon: <MedalIcon />, hidden: true }, // Hidden - set to false to reinstate
  ];

  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  // Close mobile nav on route change
  useEffect(() => {
    if (mobileOpen) onToggleMobile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // Lock body scroll when mobile or desktop nav is open
  useEffect(() => {
    if (mobileOpen || desktopOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen, desktopOpen]);

  /** Shared inner sidebar panel */
  const SidebarPanel = ({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) => (
    <div
      className={cn(
        "flex flex-col h-full bg-brand-secondary transition-all duration-300",
        expanded ? "w-56" : "w-[76px]"
      )}
    >
      {expanded ? (
        /* Expanded header: logo + name on left, hamburger on right */
        <div className="flex items-center justify-between px-4 py-5 shrink-0">
          <div className="flex items-center gap-2">
            {/* StoreInsight cart logo */}
            <svg width="28" height="24" viewBox="0 0 35 30" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M1 1H5.5L8.5 18H27.5L31 6H11" stroke="#577DF7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="12" cy="24" r="2.5" fill="#577DF7"/>
              <circle cx="24" cy="24" r="2.5" fill="#577DF7"/>
            </svg>
            <span className="text-white font-bold tracking-wide text-base whitespace-nowrap">StoreInsight</span>
          </div>
          <button
            onClick={onToggle}
            className="flex items-center justify-center w-9 h-9 text-white hover:opacity-90 shrink-0"
            aria-label="Collapse menu"
          >
            <HamburgerIcon />
          </button>
        </div>
      ) : (
        /* Collapsed header: just centered hamburger */
        <div className="flex justify-center items-center py-6 px-4 shrink-0">
          <button
            onClick={onToggle}
            className="flex items-center justify-center w-9 h-9 text-white hover:opacity-90 shrink-0"
            aria-label="Expand menu"
          >
            <HamburgerIcon />
          </button>
        </div>
      )}

      {/* Nav items */}
      <div className="flex flex-col gap-1 px-2 flex-1 overflow-y-auto">
        {navItems.filter(item => !item.hidden).map((item) => (
          <Link
            key={item.path}
            to={item.path}
            title={!expanded ? item.label : undefined}
            data-testid={item.path === "/" ? "nav-dashboard" : item.path === "/smart-actions" ? "nav-smart-actions" : undefined}
            className={cn(
              "relative flex items-center gap-3 rounded-lg transition-colors duration-200 group",
              expanded ? "px-3 py-4" : "px-[14px] py-4 justify-center",
              isActive(item.path)
                ? "bg-white/20 text-white"
                : "text-white/70 hover:text-white hover:bg-white/10"
            )}
          >
            <span className="shrink-0">{item.icon}</span>
            {expanded && (
              <span className="font-dm-sans text-sm font-medium whitespace-nowrap overflow-hidden">
                {item.label}
              </span>
            )}
            {item.badge !== undefined && (
              <span
                className={cn(
                  "absolute flex items-center justify-center h-5 min-w-[20px] px-1 rounded-full bg-app-error text-white text-xs font-normal leading-none",
                  expanded ? "top-2 right-2" : "top-2 right-1"
                )}
                data-testid={item.path === "/smart-actions" ? "nav-smart-actions-badge" : undefined}
              >
                {item.badge}
              </span>
            )}
            {!expanded && (
              <span className="pointer-events-none absolute left-full ml-3 px-2 py-1 rounded bg-gray-900 text-white text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-50">
                {item.label}
                {item.badge !== undefined && ` (${item.badge})`}
              </span>
            )}
          </Link>
        ))}
      </div>

      {/* Bottom: dark mode + logout */}
      <div className="flex flex-col gap-1 px-2 pb-6 shrink-0">
        <button
          onClick={onToggleDarkMode}
          data-testid="nav-dark-mode-toggle"
          className={cn(
            "relative flex items-center gap-3 rounded-lg transition-colors duration-200 text-white/70 hover:text-white hover:bg-white/10",
            expanded ? "px-3 py-4" : "px-[14px] py-4 justify-center"
          )}
          title={!expanded ? (darkMode ? "Light mode" : "Dark mode") : undefined}
        >
          <span className="shrink-0">{darkMode ? <SunIcon /> : <MoonIcon />}</span>
          {expanded && (
            <span className="font-dm-sans text-sm font-medium whitespace-nowrap">
              {darkMode ? "Light mode" : "Dark mode"}
            </span>
          )}
        </button>
        <button
          onClick={handleLogout}
          data-testid="nav-logout"
          className={cn(
            "relative flex items-center gap-3 rounded-lg transition-colors duration-200 text-white/70 hover:text-white hover:bg-white/10",
            expanded ? "px-3 py-4" : "px-[14px] py-4 justify-center"
          )}
          title={!expanded ? "Log out" : undefined}
          aria-label="Log out"
        >
          <span className="shrink-0"><LogoutIcon /></span>
          {expanded && (
            <span className="font-dm-sans text-sm font-medium whitespace-nowrap">Log out</span>
          )}
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* ── Desktop sidebar: unified element that responds to breakpoints ── */}
      <nav className={cn(
        "hidden md:flex h-screen shrink-0 transition-all duration-300 ease-in-out",
        desktopOpen ? "z-40" : "z-20"
      )}>
        <SidebarPanel expanded={desktopOpen} onToggle={onToggleDesktop} />
      </nav>

      {/* ── Medium desktop: backdrop when expanded (hidden on lg+) ── */}
      <div
        className={cn(
          "hidden md:block lg:hidden fixed inset-0 z-30 bg-black/50 transition-opacity duration-300",
          desktopOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onToggleDesktop}
        aria-hidden="true"
      />

      {/* ── Mobile: hamburger trigger button ── */}
      <button
        className="md:hidden fixed top-7 left-4 z-40 flex items-center justify-center w-10 h-10 rounded-full text-black"
        onClick={onToggleMobile}
        aria-label="Open menu"
      >
        {mobileOpen ? (
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="4" y1="4" x2="16" y2="16"/>
            <line x1="16" y1="4" x2="4" y2="16"/>
          </svg>
        ) : (
          <HamburgerIcon />
        )}
      </button>

      {/* ── Mobile: slide-over overlay ── */}
      {/* Backdrop */}
      <div
        className={cn(
          "md:hidden fixed inset-0 z-30 bg-black/50 transition-opacity duration-300",
          mobileOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onToggleMobile}
        aria-hidden="true"
      />
      {/* Panel */}
      <div
        className={cn(
          "md:hidden fixed inset-y-0 left-0 z-40 flex h-full transition-transform duration-300 ease-in-out",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <SidebarPanel expanded={true} onToggle={onToggleMobile} />
      </div>
    </>
  );
}
