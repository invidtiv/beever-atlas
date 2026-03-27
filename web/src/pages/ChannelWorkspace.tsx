import { useParams, Outlet, NavLink } from "react-router-dom";

const tabs = [
  { to: "wiki", label: "Wiki" },
  { to: "ask", label: "Ask" },
  { to: "memories", label: "Memories" },
  { to: "graph", label: "Graph" },
  { to: "settings", label: "Settings" },
];

export function ChannelWorkspace() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-4 px-6 pt-4 pb-0">
        <h2 className="text-lg font-semibold text-slate-900">#{id}</h2>
      </div>
      <nav className="flex gap-1 px-6 pt-2 border-b border-slate-200">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                isActive
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
