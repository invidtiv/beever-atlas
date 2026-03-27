import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquare,
  Search,
  Network,
  Settings,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { HealthBadge } from "./HealthBadge";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/channels", icon: MessageSquare, label: "Channels" },
  { to: "/search", icon: Search, label: "Search" },
  { to: "/graph", icon: Network, label: "Graph Explorer" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`flex flex-col border-r border-slate-200 bg-white transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex items-center justify-between p-4 border-b border-slate-200">
        {!collapsed && (
          <span className="text-lg font-semibold text-indigo-600">
            Beever Atlas
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-md hover:bg-slate-100 text-slate-500"
        >
          {collapsed ? <PanelLeft size={20} /> : <PanelLeftClose size={20} />}
        </button>
      </div>

      <nav className="flex-1 py-2">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? "text-indigo-600 bg-indigo-50 border-r-2 border-indigo-600"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
              } ${collapsed ? "justify-center px-2" : ""}`
            }
          >
            <Icon size={20} />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-200">
        <HealthBadge collapsed={collapsed} />
      </div>
    </aside>
  );
}
