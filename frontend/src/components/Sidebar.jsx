import { NavLink, Link } from "react-router-dom";
import { useContext } from "react";
import {
  FaHome, FaImage, FaVideo, FaExclamationTriangle,
  FaInfoCircle, FaShieldAlt, FaMoon, FaSun,
} from "react-icons/fa";
import { ThemeContext } from "../context/ThemeContext";

const NAV_LINKS = [
  { to: "/dashboard",       icon: <FaHome />,              label: "Dashboard",        end: true  },
  { to: "/image-detection", icon: <FaImage />,             label: "Image Detection",  end: false },
  { to: "/video-detection", icon: <FaVideo />,             label: "Video Detection",  end: false },
  { to: "/violations",      icon: <FaExclamationTriangle />, label: "Violations",     end: false },
  { to: "/about",           icon: <FaInfoCircle />,        label: "About",            end: false },
];

function Sidebar() {
  const { darkMode, setDarkMode } = useContext(ThemeContext);

  return (
    <div className="w-60 h-screen sticky top-0 bg-slate-950/80 backdrop-blur-xl border-r border-white/[0.06] flex flex-col p-5 z-20">
      {/* Logo */}
      <Link to="/" className="flex items-center gap-3 mb-10 hover:opacity-80 transition-opacity">
        <div className="bg-gradient-to-br from-blue-500 to-cyan-400 p-2.5 rounded-xl shadow-lg shadow-blue-500/20 flex-shrink-0">
          <FaShieldAlt className="text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-white tracking-tight leading-tight">
            SafeVision<span className="text-blue-400">AI</span>
          </h1>
          <p className="text-[10px] text-slate-500 uppercase tracking-widest">PPE Monitoring</p>
        </div>
      </Link>

      {/* Navigation */}
      <nav className="flex-1 space-y-1">
        <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest px-3 mb-3">Monitor</p>
        {NAV_LINKS.map(({ to, icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                isActive
                  ? "bg-blue-600/15 text-blue-400 border border-blue-500/25 shadow-[0_0_12px_rgba(59,130,246,0.1)]"
                  : "text-slate-400 hover:text-white hover:bg-white/[0.04] border border-transparent"
              }`
            }
          >
            <span className="text-base flex-shrink-0">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Divider */}
      <div className="border-t border-white/[0.06] pt-4 mt-2">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all duration-200"
        >
          {darkMode
            ? <><FaSun className="text-yellow-400 text-base" /> Light Mode</>
            : <><FaMoon className="text-blue-400 text-base" /> Dark Mode</>
          }
        </button>
      </div>
    </div>
  );
}

export default Sidebar;
