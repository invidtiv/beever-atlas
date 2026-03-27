import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { Dashboard } from "@/pages/Dashboard";
import { Channels } from "@/pages/Channels";
import { ChannelWorkspace } from "@/pages/ChannelWorkspace";
import { SearchPage } from "@/pages/SearchPage";
import { GraphExplorer } from "@/pages/GraphExplorer";
import { SettingsPage } from "@/pages/SettingsPage";
import { NotFound } from "@/pages/NotFound";
import { TierBrowser } from "@/components/memories/TierBrowser";

function PlaceholderTab({ label }: { label: string }) {
  return (
    <div className="p-6">
      <p className="text-slate-500">{label} — coming soon.</p>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Header />
          <main className="flex-1 overflow-auto bg-slate-50">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/channels" element={<Channels />} />
              <Route path="/channels/:id" element={<ChannelWorkspace />}>
                <Route index element={<Navigate to="wiki" replace />} />
                <Route path="wiki" element={<PlaceholderTab label="Wiki" />} />
                <Route path="ask" element={<PlaceholderTab label="Ask" />} />
                <Route path="memories" element={<TierBrowser />} />
                <Route path="graph" element={<PlaceholderTab label="Graph" />} />
                <Route path="settings" element={<PlaceholderTab label="Channel Settings" />} />
              </Route>
              <Route path="/search" element={<SearchPage />} />
              <Route path="/graph" element={<GraphExplorer />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
