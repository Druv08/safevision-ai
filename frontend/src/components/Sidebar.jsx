import { NavLink, Link } from "react-router-dom";
import { useContext } from "react";

import {
  FaHome,
  FaImage,
  FaVideo,
  FaExclamationTriangle,
  FaInfoCircle,
  FaShieldAlt,
  FaMoon,
  FaSun
} from "react-icons/fa";

import {
  ThemeContext
} from "../context/ThemeContext";
function Sidebar() {
  const {
    darkMode,
    setDarkMode
  } = useContext(
    ThemeContext
  );

  const navClass = ({
    isActive
  }) =>
    `flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all ${
      isActive
        ? "bg-blue-600 text-white"
        : darkMode
        ? "text-gray-300 hover:bg-slate-800"
        : "text-gray-700 hover:bg-gray-200"
    }`;

  return (
    <div
      className={`w-60 h-screen sticky top-0 p-5 border-r transition-all ${
        darkMode
          ? "bg-slate-950 text-white border-slate-800"
          : "bg-white text-black border-gray-200"
      }`}
    >
      <div className="mb-10">

        <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-all">

          <div className="bg-blue-600 p-2.5 rounded-xl text-white">
            <FaShieldAlt />
          </div>

          <div>
            <h1 className="text-xl font-semibold text-black dark:text-white">
              SafeVision AI
            </h1>

            <p
              className={`text-xs ${
                darkMode
                  ? "text-gray-400"
                  : "text-gray-500"
              }`}
            >
              PPE Monitoring
            </p>
          </div>

        </Link>

      </div>

      <button
        onClick={() =>
          setDarkMode(
            !darkMode
          )
        }
        className="w-full mb-6 bg-blue-600 text-white py-2 rounded-lg flex items-center justify-center gap-2"
      >
        {darkMode ? (
          <>
            <FaSun />
            Light Mode
          </>
        ) : (
          <>
            <FaMoon />
            Dark Mode
          </>
        )}
      </button>

      <ul className="space-y-2">

        <li>
          <NavLink
            to="/dashboard"
            end
            className={navClass}
          >
            <FaHome />
            Dashboard
          </NavLink>
        </li>

        <li>
          <NavLink
            to="/image-detection"
            className={navClass}
          >
            <FaImage />
            Image Detection
          </NavLink>
        </li>

        <li>
          <NavLink
            to="/video-detection"
            className={navClass}
          >
            <FaVideo />
            Video Detection
          </NavLink>
        </li>

        <li>
          <NavLink
            to="/violations"
            className={navClass}
          >
            <FaExclamationTriangle />
            Violations
          </NavLink>
        </li>

        <li>
          <NavLink
            to="/about"
            className={navClass}
          >
            <FaInfoCircle />
            About
          </NavLink>
        </li>

      </ul>
    </div>
  );
}

export default Sidebar;