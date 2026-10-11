import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell,
} from "recharts";
import {
  LuTriangleAlert, LuInbox, LuHardHat, LuShirt, LuRefreshCw, LuArrowRight, LuChartBar, LuImage, LuCloudOff,
} from "react-icons/lu";
import API, { apiError } from "../services/api";
import { useHealth } from "../services/health";
import { useTheme } from "../context/ThemeContext";
import { chartTheme, SOURCE_LABEL, STATUS_META } from "../theme";
import {
  PageHeader, SectionTitle, StatCard, Segmented, Alert, EmptyState, SeverityBadge, StatusBadge,
} from "../components/ui";

const SAMPLE = 500; // rows fetched for the charts (the API maximum per page)
const HOUR = 3600e3;
const DAY = 24 * HOUR;
const RANGES = [
  { value: "24h", label: "24h", ms: DAY, text: "in the last 24 hours" },
  { value: "7d", label: "7d", ms: 7 * DAY, text: "in the last 7 days" },
  { value: "30d", label: "30d", ms: 30 * DAY, text: "in the last 30 days" },
  { value: "all", label: "All", ms: null, text: "all time" },
];

/** Zero-filled time buckets so quiet periods show as zero instead of vanishing. */
function bucketize(rows, range) {
  const now = new Date();
  const hourly = range.value === "24h";
  const step = hourly ? HOUR : DAY;
  const floor = (d) => {
    const t = new Date(d);
    if (hourly) t.setMinutes(0, 0, 0); else t.setHours(0, 0, 0, 0);
    return t.getTime();
  };
  const oldest = rows.length ? Math.min(...rows.map((r) => new Date(r.created_at).getTime())) : now.getTime();
  const start = floor(range.ms ? now.getTime() - range.ms + step : oldest);
  const end = floor(now);
  // ponytail: one bar per day; switch to weekly buckets if "All" spans many months.
  const buckets = new Map();
  for (let t = start; t <= end; t += step) {
    // DST days aren't exactly 24h; re-floor so keys stay aligned.
    const key = floor(t);
    buckets.set(key, {
      label: new Date(key).toLocaleString(undefined, hourly ? { hour: "numeric" } : { month: "short", day: "numeric" }),
      "Helmet missing": 0,
      "Vest missing": 0,
    });
  }
  for (const r of rows) {
    const b = buckets.get(floor(r.created_at));
    if (b) b[r.type === "no_helmet" ? "Helmet missing" : "Vest missing"] += 1;
  }
  return [...buckets.values()];
}

function Dashboard() {
  const { theme } = useTheme();
  // Recompute chart colours from the CSS tokens whenever the theme flips.
  const chart = useMemo(() => chartTheme(), [theme]); // eslint-disable-line react-hooks/exhaustive-deps
  const health = useHealth();

  const [rangeKey, setRangeKey] = useState("7d");
  const range = RANGES.find((r) => r.value === rangeKey);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState(null);

  const requestId = useRef(0);

  // Effect-driven loads show skeletons; only the Refresh button shows a spinner.
  const load = useCallback(async () => {
    const id = ++requestId.current;
    const base = range.ms ? { date_from: new Date(Date.now() - range.ms).toISOString() } : {};
    const count = (params) => API.get("/violations", { params: { ...base, ...params, page_size: 1 } }).then((r) => r.data.count);
    try {
      const [list, open, helmet, vest] = await Promise.all([
        API.get("/violations", { params: { ...base, page_size: SAMPLE } }).then((r) => r.data),
        count({ status: "new" }),
        count({ type: "no_helmet" }),
        count({ type: "no_vest" }),
      ]);
      if (id !== requestId.current) return; // a newer request (e.g. another range) won
      setData({ rows: list.violations, total: list.count, open, helmet, vest });
      setError("");
      setUpdatedAt(new Date());
    } catch (e) {
      if (id === requestId.current) setError(apiError(e, "Could not load dashboard data."));
    }
  }, [range.ms]);

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load() only sets state after its await
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const changeRange = (v) => { setData(null); setRangeKey(v); };

  const trend = useMemo(() => (data ? bucketize(data.rows, range) : []), [data, range]);
  const breakdown = useMemo(() => {
    if (!data) return null;
    const by = (key) => data.rows.reduce((acc, r) => ({ ...acc, [r[key]]: (acc[r[key]] || 0) + 1 }), {});
    return { source: by("source"), status: by("status") };
  }, [data]);

  const loading = !data && !error;
  const unavailable = !data && !!error; // failed load: never present that as "no violations"
  const sampled = data && data.total > data.rows.length;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description={`PPE violations logged from image, video and live camera analysis ${range.text}.`}
        actions={
          <>
            <Segmented label="Time range" value={rangeKey} onChange={changeRange} options={RANGES} />
            <button onClick={refresh} disabled={refreshing} className="btn btn-secondary" aria-label="Refresh data" data-tip={updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : "Refresh"} data-tip-align="end">
              <LuRefreshCw className={refreshing ? "animate-spin" : ""} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </>
        }
      />

      {error && (
        <Alert className="mb-6" onRetry={refresh} title={data ? "Showing the last loaded data" : "Dashboard data is unavailable"}>
          {error}
        </Alert>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 sm:gap-4">
        <StatCard label="Violations" icon={LuTriangleAlert} tone="tone-danger" loading={loading} value={data?.total ?? "—"} hint={range.text} />
        <StatCard label="Awaiting review" icon={LuInbox} tone="tone-warning" loading={loading} value={data?.open ?? "—"} hint="Status: new" />
        <StatCard label="Helmet missing" icon={LuHardHat} tone="tone-danger" loading={loading} value={data?.helmet ?? "—"} hint="High severity" />
        <StatCard label="Vest missing" icon={LuShirt} tone="tone-warning" loading={loading} value={data?.vest ?? "—"} hint="Medium severity" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <section className="card p-4 sm:p-5 lg:col-span-2 min-w-0" aria-label="Violations over time">
          <SectionTitle
            title="Violations over time"
            description={sampled ? `Chart covers the latest ${data.rows.length} of ${data.total} records` : `By violation type, ${range.value === "24h" ? "per hour" : "per day"}`}
          />
          {loading ? (
            <div className="skeleton h-[260px]" />
          ) : unavailable ? (
            <Unavailable />
          ) : !data?.total ? (
            <EmptyState icon={LuChartBar} title="No violations in this period" className="h-[260px]">
              Pick a longer time range, or run a detection to start collecting data.
            </EmptyState>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={trend} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={chart.grid} />
                <XAxis dataKey="label" tick={chart.axis} axisLine={false} tickLine={false} minTickGap={16} />
                <YAxis allowDecimals={false} tick={chart.axis} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chart.tooltip} cursor={chart.cursor} />
                <Bar dataKey="Helmet missing" stackId="v" fill={chart.helmet} maxBarSize={36} />
                <Bar dataKey="Vest missing" stackId="v" fill={chart.vest} radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          )}
          {!!data?.total && (
            <div className="flex gap-4 mt-3 text-xs text-muted">
              <Legend color={chart.helmet} label="Helmet missing" />
              <Legend color={chart.vest} label="Vest missing" />
            </div>
          )}
        </section>

        <section className="card p-4 sm:p-5 min-w-0" aria-label="Violations by type">
          <SectionTitle title="By violation type" description={range.text} />
          {loading ? (
            <div className="skeleton h-[260px]" />
          ) : unavailable ? (
            <Unavailable />
          ) : !data?.total ? (
            <EmptyState title="No data" className="h-[260px]">Nothing logged {range.text}.</EmptyState>
          ) : (
            <>
              <div className="relative">
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={[{ name: "Helmet missing", value: data.helmet }, { name: "Vest missing", value: data.vest }]}
                      dataKey="value" innerRadius={62} outerRadius={88} paddingAngle={2} stroke="none"
                    >
                      <Cell fill={chart.helmet} />
                      <Cell fill={chart.vest} />
                    </Pie>
                    <Tooltip contentStyle={chart.tooltip} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-2xl font-semibold tabular-nums">{data.total}</span>
                  <span className="text-xs text-muted">total</span>
                </div>
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                {[["Helmet missing", data.helmet, chart.helmet], ["Vest missing", data.vest, chart.vest]].map(([label, n, c]) => (
                  <div key={label} className="flex items-center justify-between">
                    <dt><Legend color={c} label={label} /></dt>
                    <dd className="tabular-nums text-fg">
                      {n} <span className="text-muted">({Math.round((n / data.total) * 100)}%)</span>
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </section>
      </div>

      {/* Breakdowns + system */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
        <BreakdownCard title="By source" unavailable={unavailable} loading={loading} counts={breakdown?.source} labels={SOURCE_LABEL} total={data?.rows.length} sampled={sampled} />
        <BreakdownCard
          title="By review status"
          unavailable={unavailable}
          loading={loading}
          counts={breakdown?.status}
          labels={Object.fromEntries(Object.entries(STATUS_META).map(([k, v]) => [k, v.label]))}
          total={data?.rows.length}
          sampled={sampled}
          action={<Link to="/violations?status=new" className="text-xs font-medium text-primary hover:underline">Review queue</Link>}
        />
        <SystemCard health={health} />
      </div>

      {/* Recent */}
      <section className="card mt-4 min-w-0" aria-label="Recent violations">
        <div className="p-4 sm:p-5 pb-0 sm:pb-0">
          <SectionTitle
            title="Recent violations"
            description="Newest records first"
            action={<Link to="/violations" className="btn btn-ghost btn-sm">View all <LuArrowRight /></Link>}
          />
        </div>
        {loading ? (
          <div className="p-5 space-y-3">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-9" />)}</div>
        ) : unavailable ? (
          <Unavailable h="" />
        ) : !data?.rows.length ? (
          <EmptyState
            icon={LuInbox}
            title="No violations in this period"
            action={<Link to="/image-detection" className="btn btn-secondary btn-sm"><LuImage /> Run an image detection</Link>}
          />
        ) : (
          <>
          <ul className="sm:hidden divide-y divide-line border-t border-line mt-4">
            {data.rows.slice(0, 6).map((v) => (
              <li key={v.id}>
                <Link to={`/violations?id=${v.id}`} state={{ violation: v }} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2">
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium truncate">{v.violation_type}</span>
                      <SeverityBadge severity={v.severity} />
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-muted tabular-nums">{new Date(v.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</span>
                      <StatusBadge status={v.status} />
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <div className="hidden sm:block overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Detected</th><th>Violation</th><th>Severity</th>
                  <th className="hidden md:table-cell">Source</th><th className="hidden sm:table-cell">Confidence</th>
                  <th>Status</th><th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {data.rows.slice(0, 6).map((v) => (
                  <tr key={v.id}>
                    <td className="text-muted tabular-nums whitespace-nowrap">{new Date(v.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</td>
                    <td className="font-medium whitespace-nowrap">{v.violation_type}</td>
                    <td><SeverityBadge severity={v.severity} /></td>
                    <td className="hidden md:table-cell text-muted whitespace-nowrap">{SOURCE_LABEL[v.source] ?? v.source}</td>
                    <td className="hidden sm:table-cell tabular-nums">{(v.confidence * 100).toFixed(1)}%</td>
                    <td><StatusBadge status={v.status} /></td>
                    <td className="text-right">
                      <Link to={`/violations?id=${v.id}`} state={{ violation: v }} className="btn btn-ghost btn-sm">Details</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </section>
    </div>
  );
}

function Unavailable({ h = "h-[260px]" }) {
  return <EmptyState icon={LuCloudOff} title="Data unavailable" className={h}>Couldn't load this from the backend.</EmptyState>;
}

function Legend({ color, label }) {
  return (
    <span className="inline-flex items-center gap-2 text-muted">
      <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} aria-hidden="true" />
      {label}
    </span>
  );
}

function BreakdownCard({ title, counts, labels, total, loading, unavailable, sampled, action }) {
  return (
    <section className="card p-4 sm:p-5 min-w-0" aria-label={title}>
      <SectionTitle title={title} description={sampled ? `Latest ${total} records` : "Share of violations in range"} action={action} />
      {loading ? (
        <div className="space-y-4">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-6" />)}</div>
      ) : unavailable || !total ? (
        <p className="text-sm text-muted py-6 text-center">{unavailable ? "Data unavailable." : "No data in this period."}</p>
      ) : (
        <ul className="space-y-3.5">
          {Object.entries(labels).map(([key, label]) => {
            const n = counts?.[key] || 0;
            const pct = Math.round((n / total) * 100);
            return (
              <li key={key}>
                <div className="flex justify-between text-sm mb-1.5">
                  <span className="text-fg">{label}</span>
                  <span className="tabular-nums text-muted">{n} · {pct}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                  <div className="h-full rounded-full bg-primary/70" style={{ width: `${pct}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function SystemCard({ health }) {
  const { data, state } = health;
  const rows = data
    ? [
        ["Backend API", "Online", "tone-ok"],
        ["Detection models", data.model?.loaded ? "Loaded" : "Unavailable", data.model?.loaded ? "tone-ok" : "tone-danger"],
        ["Database", data.database?.mode === "local" ? "Local dev store" : data.database?.connected ? "Connected" : "Unreachable",
          data.database?.connected ? (data.database?.mode === "local" ? "tone-warning" : "tone-ok") : "tone-danger"],
        ["Disk space", `${(data.disk?.free_mb / 1024).toFixed(1)} GB free`, data.disk?.ok ? "tone-ok" : "tone-warning"],
      ]
    : [];
  return (
    <section className="card p-4 sm:p-5 min-w-0 md:col-span-2 xl:col-span-1" aria-label="System health">
      <SectionTitle
        title="System health"
        description="Live from the backend /health check"
        action={<Link to="/about" className="text-xs font-medium text-primary hover:underline">Details</Link>}
      />
      {state === "checking" ? (
        <div className="space-y-3">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-6" />)}</div>
      ) : state === "offline" ? (
        <Alert onRetry={health.refresh}>The backend is not responding.</Alert>
      ) : (
        <ul className="divide-y divide-line">
          {rows.map(([label, value, tone]) => (
            <li key={label} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0 text-sm">
              <span className="text-muted">{label}</span>
              <span className={`badge ${tone}`}><span className="dot" />{value}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default Dashboard;
