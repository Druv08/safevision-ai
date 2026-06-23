import { useContext } from "react";

import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";

import {
  ThemeContext
} from "../context/ThemeContext";

function MainLayout({
  children
}) {
  const { darkMode } =
    useContext(ThemeContext);

  return (
    <div
      className={`flex min-h-screen transition-all duration-300 ${
        darkMode
          ? "bg-slate-900 text-white"
          : "bg-gray-100 text-black"
      }`}
    >
      <Sidebar />

      <div className="flex-1">
        <Navbar />

        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export default MainLayout;