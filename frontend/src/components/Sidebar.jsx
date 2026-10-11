import { NavLink, Link } from "react-router-dom";
import { LuX, LuLogOut, LuPanelLeftClose, LuPanelLeftOpen } from "react-icons/lu";
import { useAuth } from "../context/AuthContext";
import { NAV_GROUPS } from "../nav";
import { Logo } from "./ui";

function Sidebar({ open, onClose, collapsed, onToggleCollapsed }) {
  const { user, role, signOut } = useAuth();
  // The rail only applies on desktop; the mobile drawer is always full width.
  const rail = collapsed ? "lg:w-16" : "lg:w-60";
  const hideInRail = collapsed ? "lg:hidden" : "";

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        aria-label="Main navigation"
        onClick={(e) => e.target.closest("a") && onClose()}
        className={`fixed lg:sticky top-0 left-0 z-40 h-screen w-64 ${rail} flex-shrink-0 flex flex-col bg-sidebar border-r border-line transition-[transform,width] duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand */}
        <div className={`h-14 flex items-center gap-2 px-4 border-b border-line ${collapsed ? "lg:justify-center lg:px-0" : ""}`}>
          <Link to="/" aria-label="SafeVisionAI home" className="min-w-0 rounded-md">
            <span className={collapsed ? "lg:hidden" : ""}><Logo /></span>
            <span className={collapsed ? "hidden lg:block" : "hidden"}><Logo compact /></span>
          </Link>
          <button onClick={onClose} aria-label="Close menu" className="btn btn-ghost btn-sm btn-icon ml-auto lg:hidden">
            <LuX />
          </button>
        </div>

        {/* Navigation */}
        <nav className={`flex-1 py-4 px-3 space-y-5 overflow-y-auto ${collapsed ? "lg:px-2 lg:overflow-visible" : ""}`}>
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p className={`px-2 mb-1.5 text-[11px] font-medium uppercase tracking-wider text-subtle ${hideInRail}`}>
                {group.label}
              </p>
              <ul className="space-y-0.5">
                {group.items.map(({ to, label, icon: Icon }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      data-tip={collapsed ? label : undefined}
                      data-tip-side="right"
                      aria-label={collapsed ? label : undefined}
                      className={({ isActive }) =>
                        `relative flex items-center gap-3 h-9 px-2.5 rounded-lg text-sm font-medium transition-colors ${
                          collapsed ? "lg:justify-center lg:px-0" : ""
                        } ${isActive ? "bg-primary/10 text-fg" : "text-muted hover:text-fg hover:bg-surface-2"}`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          {isActive && <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-primary" aria-hidden="true" />}
                          <Icon className={`text-[1.05rem] flex-shrink-0 ${isActive ? "text-primary" : ""}`} aria-hidden="true" />
                          <span className={`truncate ${hideInRail}`}>{label}</span>
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {/* Account */}
        <div className={`border-t border-line p-3 space-y-1 ${collapsed ? "lg:px-2" : ""}`}>
          <div className={`flex items-center gap-2.5 px-1.5 py-1.5 ${collapsed ? "lg:justify-center lg:px-0" : ""}`}>
            <span
              className="w-8 h-8 rounded-full bg-surface-2 border border-line flex items-center justify-center text-xs font-semibold text-fg uppercase flex-shrink-0"
              title={user?.email}
              aria-hidden="true"
            >
              {user?.email?.[0] ?? "?"}
            </span>
            <div className={`min-w-0 flex-1 ${hideInRail}`}>
              <p className="text-sm font-medium text-fg truncate" title={user?.email}>{user?.email}</p>
              <p className="text-xs text-muted capitalize">{role || "…"}</p>
            </div>
            <button onClick={signOut} aria-label="Log out" data-tip="Log out" className={`btn btn-ghost btn-sm btn-icon ${hideInRail}`}>
              <LuLogOut />
            </button>
          </div>
          <button
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            data-tip={collapsed ? "Expand sidebar" : undefined}
            data-tip-side="right"
            className={`hidden lg:flex btn btn-ghost btn-sm ${collapsed ? "btn-icon mx-auto" : "w-full justify-start"}`}
          >
            {collapsed ? <LuPanelLeftOpen /> : <><LuPanelLeftClose /> Collapse</>}
          </button>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
