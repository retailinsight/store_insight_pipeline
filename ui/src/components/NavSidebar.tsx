import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useSmartActions } from "@/contexts/SmartActionsContext";
import { useAppDispatch } from "@/store/hooks";
import { logout as logoutAction } from "@/store/slices/authSlice";
import { clearKpis } from "@/store/slices/kpisSlice";
import { clearSuccesses } from "@/store/slices/successesSlice";
import { clearActions } from "@/store/slices/actionsSlice";
import { useToast } from "@/hooks/useToast";
import { initiateLogout } from "@/utils/auth/oauthFlow";
import {
  DashboardIcon,
  SmartActionsIcon,
  ChatIcon,
  MedalLargeIcon,
  LogoutIcon,
  SunIcon,
  MoonIcon,
  HamburgerIcon,
  CloseStrokeIcon,
  LogoIcon,
} from "@/components/icons";

interface NavItem {
  path: string;
  label: string;
  badge?: number;
  icon: React.ReactNode;
  hidden?: boolean;
}

interface NavSidebarProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  mobileOpen: boolean;
  onToggleMobile: () => void;
  desktopOpen: boolean;
  onToggleDesktop: () => void;
}

export default function NavSidebar({
  darkMode,
  onToggleDarkMode,
  mobileOpen,
  onToggleMobile,
  desktopOpen,
  onToggleDesktop,
}: NavSidebarProps) {
  const location = useLocation();
  const { getVisibleActions, getActionsByStatus } = useSmartActions();
  const dispatch = useAppDispatch();
  const { toast } = useToast();

  const handleLogout = () => {
    toast({
      title: "Successfully logged out",
      description: "See you next time!",
    });
    // initiateLogout reads the token first, then clears it and redirects.
    // Dispatch Redux cleanup after so the token is still available for revoke.
    initiateLogout();
    dispatch(logoutAction());
    dispatch(clearKpis());
    dispatch(clearSuccesses());
    dispatch(clearActions());
  };

  const pendingAndReminderCount = getVisibleActions().length;
  const completedSuccessesCount = getActionsByStatus("completed").length;

  const showChat = import.meta.env.VITE_AI_CHAT !== "false";

  const navItems: NavItem[] = [
    { path: "/", label: "Dashboard", icon: <DashboardIcon /> },
    {
      path: "/smart-actions",
      label: "Smart Actions",
      badge: pendingAndReminderCount,
      icon: <SmartActionsIcon />,
    },
    {
      path: "/chat",
      label: "Chat",
      icon: <ChatIcon />,
      hidden: !showChat,
    },
    {
      path: "/successes",
      label: "Successes",
      badge: completedSuccessesCount,
      icon: <MedalLargeIcon size={26} />,
      hidden: true,
    },
  ];

  const isActive = (path: string) =>
    path === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(path);

  useEffect(() => {
    if (mobileOpen) onToggleMobile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  useEffect(() => {
    if (mobileOpen || desktopOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen, desktopOpen]);

  const SidebarPanel = ({
    expanded,
    onToggle,
  }: {
    expanded: boolean;
    onToggle: () => void;
  }) => (
    <div
      className={cn(
        "flex flex-col h-full bg-brand-secondary transition-all duration-300",
        expanded ? "w-56" : "w-[76px]",
      )}
    >
      {expanded ? (
        <div className="flex items-center justify-between px-4 py-5 shrink-0">
          <div className="flex items-center gap-2">
            <LogoIcon />
            <span className="text-white font-bold tracking-wide text-base whitespace-nowrap">
              StoreInsight
            </span>
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
        {navItems
          .filter((item) => !item.hidden)
          .map((item) => (
            <Link
              key={item.path}
              to={item.path}
              title={!expanded ? item.label : undefined}
              className={cn(
                "relative flex items-center gap-3 rounded-lg transition-colors duration-200 group",
                expanded ? "px-3 py-4" : "px-[14px] py-4 justify-center",
                isActive(item.path)
                  ? "bg-white/20 text-white"
                  : "text-white/70 hover:text-white hover:bg-white/10",
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
                    expanded ? "top-2 right-2" : "top-2 right-1",
                  )}
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

      <div className="flex flex-col gap-1 px-2 pb-6 shrink-0">
        <button
          onClick={onToggleDarkMode}
          className={cn(
            "relative flex items-center gap-3 rounded-lg transition-colors duration-200 text-white/70 hover:text-white hover:bg-white/10",
            expanded ? "px-3 py-4" : "px-[14px] py-4 justify-center",
          )}
          title={
            !expanded ? (darkMode ? "Light mode" : "Dark mode") : undefined
          }
        >
          <span className="shrink-0">
            {darkMode ? <SunIcon /> : <MoonIcon />}
          </span>
          {expanded && (
            <span className="font-dm-sans text-sm font-medium whitespace-nowrap">
              {darkMode ? "Light mode" : "Dark mode"}
            </span>
          )}
        </button>
        <button
          onClick={handleLogout}
          className={cn(
            "relative flex items-center gap-3 rounded-lg transition-colors duration-200 text-white/70 hover:text-white hover:bg-white/10",
            expanded ? "px-3 py-4" : "px-[14px] py-4 justify-center",
          )}
          title={!expanded ? "Log out" : undefined}
          aria-label="Log out"
        >
          <span className="shrink-0">
            <LogoutIcon />
          </span>
          {expanded && (
            <span className="font-dm-sans text-sm font-medium whitespace-nowrap">
              Log out
            </span>
          )}
        </button>
      </div>
    </div>
  );

  return (
    <>
      <nav
        className={cn(
          "hidden md:flex h-screen shrink-0 transition-all duration-300 ease-in-out",
          desktopOpen ? "z-40" : "z-20",
        )}
      >
        <SidebarPanel expanded={desktopOpen} onToggle={onToggleDesktop} />
      </nav>

      <div
        className={cn(
          "hidden md:block lg:hidden fixed inset-0 z-30 bg-black/50 transition-opacity duration-300",
          desktopOpen
            ? "opacity-100 pointer-events-auto"
            : "opacity-0 pointer-events-none",
        )}
        onClick={onToggleDesktop}
        aria-hidden="true"
      />

      <button
        className="md:hidden fixed top-7 left-4 z-40 flex items-center justify-center w-10 h-10 rounded-full text-black"
        onClick={onToggleMobile}
        aria-label="Open menu"
      >
        {mobileOpen ? <CloseStrokeIcon /> : <HamburgerIcon />}
      </button>

      <div
        className={cn(
          "md:hidden fixed inset-0 z-30 bg-black/50 transition-opacity duration-300",
          mobileOpen
            ? "opacity-100 pointer-events-auto"
            : "opacity-0 pointer-events-none",
        )}
        onClick={onToggleMobile}
        aria-hidden="true"
      />
      <div
        className={cn(
          "md:hidden fixed inset-y-0 left-0 z-40 flex h-full transition-transform duration-300 ease-in-out",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <SidebarPanel expanded={true} onToggle={onToggleMobile} />
      </div>
    </>
  );
}
