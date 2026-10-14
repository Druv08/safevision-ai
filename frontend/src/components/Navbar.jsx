import { Link, useLocation } from "react-router-dom";
import { LuMenu, LuSun, LuMoon, LuChevronRight } from "react-icons/lu";
import { useTheme } from "../context/ThemeContext";
import { useHealth } from "../services/health";
import { NAV_ITEMS } from "../nav";
import { Logo } from "./ui";

const STATUS = {
  checking: { tone: "tone-neutral", label: "Checking…" },
  ok:       { tone: "tone-ok",      label: "All systems operational" },
  degraded: { tone: "tone-warning", label: "Degraded" },
  offline:  { tone: "tone-danger",  label: "Backend offline" },
};

function Navbar({ onMenu }) {
  const { pathname } = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { state } = useHealth(30000);
  const page = NAV_ITEMS.find((i) => i.to === pathname);
  const s = STATUS[state];
  const isDark = theme === "dark";

  return (
    <header className="sticky top-0 z-20 h-14 flex items-center gap-3 px-4 sm:px-6 lg:px-8 border-b border-line bg-canvas/85 backdrop-blur">
      <button onClick={onMenu} aria-label="Open menu" className="btn btn-ghost btn-icon -ml-2 lg:hidden">
        <LuMenu />
      </button>
      <Link to="/dashboard" className="lg:hidden rounded-md" aria-label="Dashboard"><Logo /></Link>

      <nav aria-label="Breadcrumb" className="hidden lg:flex items-center gap-1.5 text-sm min-w-0">
        <span className="text-muted">{page?.group ?? "SafeVisionAI"}</span>
        {page && (
          <>
            <LuChevronRight className="text-subtle" aria-hidden="true" />
            <span className="text-fg font-medium truncate" aria-current="page">{page.label}</span>
          </>
        )}
      </nav>

      <div className="ml-auto flex items-center gap-1.5">
        <Link
          to="/about"
          role="status"
          aria-label={`System status: ${s.label}`}
          title="Open system information"
          className={`${s.tone} badge h-7 px-2.5 hover:opacity-85`}
        >
          <span className={`dot ${state === "ok" ? "animate-live" : ""}`} />
          <span className="hidden sm:inline">{s.label}</span>
        </Link>
        <button
          onClick={toggleTheme}
          aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
          data-tip={isDark ? "Light theme" : "Dark theme"}
          data-tip-align="end"
          className="btn btn-ghost btn-icon"
        >
          {isDark ? <LuSun /> : <LuMoon />}
        </button>
      </div>
    </header>
  );
}

export default Navbar;
