import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface ChartBlockProps {
  spec: string;
}

interface ChartSpec {
  type?: "bar" | "area" | "donut" | "pie";
  title?: string;
  data: Record<string, unknown>[];
  xKey?: string;
  series?: string[];
  colors?: string[];
  // LLM may use alternative field names
  categoryField?: string;
  valueField?: string;
  nameKey?: string;
  dataKey?: string;
}

const DEFAULT_COLORS = ["#6366f1", "#f59e0b", "#22c55e", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

function normalizeSpec(raw: Record<string, unknown>): ChartSpec {
  const spec = raw as unknown as ChartSpec;
  // Normalize type
  let type = spec.type ?? "donut";
  if (type === "pie") type = "donut";

  // Normalize xKey: try xKey, categoryField, nameKey, or auto-detect first string key
  const data = Array.isArray(spec.data) ? spec.data : [];
  const firstRow = data[0] as Record<string, unknown> | undefined;
  let xKey = spec.xKey || spec.categoryField || spec.nameKey || "";
  let series = spec.series || [];

  if (firstRow && (!xKey || series.length === 0)) {
    // Auto-detect: first string-valued key is xKey, numeric keys are series
    const keys = Object.keys(firstRow);
    for (const k of keys) {
      if (!xKey && typeof firstRow[k] === "string") xKey = k;
      else if (typeof firstRow[k] === "number") {
        if (!series.includes(k)) series.push(k);
      }
    }
    // If valueField is specified, use it as series
    if (series.length === 0 && spec.valueField) {
      series = [spec.valueField];
    }
    if (series.length === 0 && spec.dataKey) {
      series = [spec.dataKey];
    }
  }

  return { ...spec, type, data, xKey, series, colors: spec.colors || DEFAULT_COLORS };
}

export function ChartBlock({ spec }: ChartBlockProps) {
  let chartSpec: ChartSpec;
  try {
    const raw = JSON.parse(spec);
    chartSpec = normalizeSpec(raw);
  } catch {
    return (
      <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950 p-4">
        <p className="text-sm text-red-800 dark:text-red-300">Invalid chart spec</p>
        <pre className="mt-2 text-xs overflow-auto text-red-600 dark:text-red-400">{spec}</pre>
      </div>
    );
  }

  const { type, title, data, xKey = "name", series = [], colors = DEFAULT_COLORS } = chartSpec;

  // Don't render empty charts
  if (!data || data.length === 0) {
    return null;
  }

  return (
    <div className="my-4">
      {title && <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">{title}</h4>}
      <ResponsiveContainer width="100%" height={300}>
        {type === "bar" ? (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            {series.map((s, i) => (
              <Bar key={s} dataKey={s} fill={colors[i % colors.length]} />
            ))}
          </BarChart>
        ) : type === "area" ? (
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            {series.map((s, i) => (
              <Area
                key={s}
                type="monotone"
                dataKey={s}
                fill={colors[i % colors.length]}
                stroke={colors[i % colors.length]}
                fillOpacity={0.3}
              />
            ))}
          </AreaChart>
        ) : (
          <PieChart>
            <Pie
              data={data}
              dataKey={series[0] || "value"}
              nameKey={xKey}
              innerRadius={60}
              outerRadius={100}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i % colors.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
