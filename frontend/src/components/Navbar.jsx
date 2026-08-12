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
  const title = PAGE_NAMES[pathname] || "SafeVisionAI";

  return (
    <div className="sv-chrome sv-bd-b px-6 py-4 flex items-center justify-between flex-shrink-0">
      <h1 className="sv-fg text-xl font-extrabold tracking-[-0.01em]">{title}</h1>
      <div className="tone-ok sv-tone sv-tone-ink sv-mono flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-[0.14em]">
        <span
          className="sv-tone-dot w-1.5 h-1.5 rounded-full"
          style={{ animation: "sv-blink 1.6s ease-in-out infinite" }}
        />
        System Online
      </div>
    </div>
  );
}

export default Navbar;
