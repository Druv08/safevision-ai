import { NavLink, Link } from "react-router-dom";
import {
  FaHome, FaImage, FaVideo, FaExclamationTriangle,
  FaInfoCircle, FaShieldAlt, FaMoon, FaSun,
} from "react-icons/fa";
import { useTheme } from "../context/ThemeContext";

const NAV_LINKS = [
  { to: "/dashboard",       icon: <FaHome />,                label: "Dashboard",       end: true  },
  { to: "/image-detection", icon: <FaImage />,               label: "Image Detection", end: false },
  { to: "/video-detection", icon: <FaVideo />,               label: "Video Detection", end: false },
  { to: "/violations",      icon: <FaExclamationTriangle />, label: "Violations",      end: false },
  { to: "/about",           icon: <FaInfoCircle />,          label: "About",           end: false },
];

function Sidebar() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <div className="sv-chrome sv-bd-r w-60 h-screen sticky top-0 flex flex-col p-5 z-20">
      {/* Logo */}
      <Link to="/" className="flex items-center gap-3 mb-10 hover:opacity-80 transition-opacity">
        <div className="sv-logo-tile w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0">
          <FaShieldAlt className="sv-ink-gold" />
        </div>
        <div className="leading-none">
          <h1 className="sv-fg text-[17px] font-extrabold tracking-[-0.01em]">
            SafeVision<span className="sv-ink-gold">AI</span>
          </h1>
          <p className="sv-mono sv-fg-dim text-[8.5px] font-bold uppercase tracking-[0.22em] mt-1">
            PPE Monitoring
          </p>
        </div>
      </Link>

      {/* Navigation */}
      <nav className="flex-1 space-y-1">
        <p className="sv-mono sv-fg-faint text-[9px] font-bold uppercase tracking-[0.2em] px-3 mb-3">
          Monitor
        </p>
        {NAV_LINKS.map(({ to, icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border ${
                isActive ? "tone-gold sv-tone sv-tone-ink" : "sv-navitem"
              }`
            }
          >
            <span className="text-base flex-shrink-0">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Theme toggle */}
      <div className="sv-bd-t pt-4 mt-2">
        <button
          onClick={toggleTheme}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          className="sv-navitem w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm"
        >
          {isDark
            ? <><FaSun className="sv-ink-gold text-base" /> Light Mode</>
            : <><FaMoon className="sv-ink-gold text-base" /> Dark Mode</>
          }
        </button>
      </div>
    </div>
  );
}

export default Sidebar;
