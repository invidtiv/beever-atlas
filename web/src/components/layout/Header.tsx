import { useLocation } from "react-router-dom";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/channels": "Channels",
  "/search": "Search",
  "/graph": "Graph Explorer",
  "/settings": "Settings",
};

export function Header() {
  const location = useLocation();

  const title =
    pageTitles[location.pathname] ??
    (location.pathname.startsWith("/channels/") ? "Channel" : "Beever Atlas");

  return (
    <header className="flex items-center h-14 px-6 border-b border-slate-200 bg-white">
      <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
    </header>
  );
}
