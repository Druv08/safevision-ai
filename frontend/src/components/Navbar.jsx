import { useLocation } from "react-router-dom";

const PAGE_NAMES = {
  "/dashboard":       "Dashboard Overview",
  "/image-detection": "Image Detection",
  "/video-detection": "Video Detection",
  "/violations":      "Violations Monitor",
  "/about":           "About",
};

function Navbar() {
  const { pathname } = useLocation();
  const title = PAGE_NAMES[pathname] || "SafeVision AI";

  return (
    <div className="bg-slate-950/70 backdrop-blur-xl border-b border-white/[0.06] px-6 py-4 flex items-center justify-between flex-shrink-0">
      <h1 className="text-xl font-bold text-white">{title}</h1>
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        System Online
      </div>
    </div>
  );
}

export default Navbar;
