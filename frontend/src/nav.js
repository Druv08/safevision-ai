import { LuLayoutDashboard, LuImage, LuFilm, LuCctv, LuTriangleAlert, LuInfo } from "react-icons/lu";

// Single source for the sidebar, breadcrumbs and routes.
export const NAV_GROUPS = [
  { label: "Overview", items: [{ to: "/dashboard", label: "Dashboard", icon: LuLayoutDashboard }] },
  {
    label: "Detection",
    items: [
      { to: "/image-detection", label: "Image Detection", icon: LuImage },
      { to: "/video-detection", label: "Video Detection", icon: LuFilm },
      { to: "/live", label: "Live Monitoring", icon: LuCctv },
    ],
  },
  { label: "Records", items: [{ to: "/violations", label: "Violations", icon: LuTriangleAlert }] },
  { label: "System", items: [{ to: "/about", label: "About & System", icon: LuInfo }] },
];

export const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items.map((i) => ({ ...i, group: g.label })));
