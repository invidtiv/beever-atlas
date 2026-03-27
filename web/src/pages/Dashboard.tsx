import { HealthBadge } from "@/components/layout/HealthBadge";

const statCards = [
  { label: "Channels Synced", value: "—" },
  { label: "Total Memories", value: "—" },
  { label: "Last Sync", value: "—" },
  { label: "Total Entities", value: "—" },
];

export function Dashboard() {
  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
          >
            <p className="text-sm text-slate-500">{card.label}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {card.value}
            </p>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-medium text-slate-700 mb-3">System Health</h2>
        <HealthBadge />
      </div>
    </div>
  );
}
