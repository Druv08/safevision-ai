import { useContext } from "react";

import {
  ThemeContext
} from "../context/ThemeContext";
function Navbar() {
  const { darkMode } =
    useContext(ThemeContext);

  return (
    <div
      className={`shadow px-6 py-4 border-b transition-all duration-300 ${
        darkMode
          ? "bg-slate-950 text-white border-slate-800"
          : "bg-white text-black border-gray-200"
      }`}
    >
      <h1 className="text-2xl font-bold">
        SafeVision AI Dashboard
      </h1>
    </div>
  );
}

export default Navbar;