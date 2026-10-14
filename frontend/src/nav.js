import { LuLayoutDashboard, LuImage, LuFilm, LuCctv, LuWebcam, LuTriangleAlert, LuInfo, LuBell } from "react-icons/lu";

// Single source for the sidebar, breadcrumbs and routes.
export const NAV_GROUPS = [
  { label: "Overview", items: [{ to: "/dashboard", label: "Dashboard", icon: LuLayoutDashboard }] },
  {
    label: "Detection",
    items: [
      { to: "/image-detection", label: "Image Detection", icon: LuImage },
      { to: "/video-detection", label: "Video Detection", icon: LuFilm },
      { to: "/live", label: "Webcam demo", icon: LuWebcam },
    ],
  },
  {
    label: "Sites",
    items: [
      { to: "/cameras", label: "Cameras & zones", icon: LuCctv },
      { to: "/alerts", label: "Alerts", icon: LuBell },
    ],
  },
  { label: "Records", items: [{ to: "/violations", label: "Violations", icon: LuTriangleAlert }] },
  { label: "System", items: [{ to: "/about", label: "About & System", icon: LuInfo }] },
];

export const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items.map((i) => ({ ...i, group: g.label })));
