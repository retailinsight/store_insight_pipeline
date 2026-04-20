import { useState, useEffect } from "react";
import NavSidebar from "./NavSidebar";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const [darkMode, setDarkMode] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Initialize based on screen size only (don't use localStorage for responsive behavior)
  const [desktopNavOpen, setDesktopNavOpen] = useState(() => {
    return window.innerWidth >= 1024;
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  // Auto-expand/collapse sidebar based on screen size
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setDesktopNavOpen(true);
      } else {
        setDesktopNavOpen(false);
      }
    };

    // Listen for resize events
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-app-bg dark:bg-brand-secondary">
      <NavSidebar
        darkMode={darkMode}
        onToggleDarkMode={() => setDarkMode(!darkMode)}
        mobileOpen={mobileNavOpen}
        onToggleMobile={() => setMobileNavOpen((v) => !v)}
        desktopOpen={desktopNavOpen}
        onToggleDesktop={() => setDesktopNavOpen((v) => !v)}
      />
      {/* Main content — full width on mobile, flex-1 on desktop */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {children}
      </main>
    </div>
  );
}
