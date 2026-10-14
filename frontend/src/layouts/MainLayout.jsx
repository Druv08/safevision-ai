import { Suspense, useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";
import { PageFallback } from "../components/ui";

const COLLAPSE_KEY = "sv-sidebar-collapsed";

function readCollapsed() {
  try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
}

function MainLayout() {
  const [navOpen, setNavOpen] = useState(false); // mobile drawer
  const [collapsed, setCollapsed] = useState(readCollapsed); // desktop rail

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      try { localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1"); } catch { /* non-fatal */ }
      return !c;
    });
  };

  return (
    <div className="flex min-h-screen bg-canvas text-fg">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-80 btn btn-primary">
        Skip to content
      </a>
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
      />
      <div className="flex-1 min-w-0 flex flex-col">
        <Navbar onMenu={() => setNavOpen(true)} />
        <main id="main" className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="max-w-7xl mx-auto w-full">
            <Suspense fallback={<PageFallback />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}

export default MainLayout;
