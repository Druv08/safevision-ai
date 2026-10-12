import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell,
} from "recharts";
import {
  LuTriangleAlert, LuInbox, LuHardHat, LuShirt, LuRefreshCw, LuArrowRight, LuChartBar, LuCloudOff, LuFileDown,
} from "react-icons/lu";
import API, { apiError, download } from "../services/api";
import { useHealth } from "../services/health";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import { chartTheme, CAUSE_LABEL, STATUS_META, TYPE_OPTIONS } from "../theme";
import { PageHeader, SectionTitle, StatCard, Segmented, Alert, EmptyState, Spinner } from "../components/ui";

const HOUR = 3600e3;
const DAY = 24 * HOUR;
const RANGES = [
  { value: "24h", label: "24h", ms: DAY, text: "in the last 24 hours" },
  { value: "7d", label: "7d", ms: 7 * DAY, text: "in the last 7 days" },
  { value: "30d", label: "30d", ms: 30 * DAY, text: "in the last 30 days" },
  { value: "all", label: "All", ms: null, text: "all time" },
];
const pct = (rate) => (rate == null ? "—" : `${Math.round(rate * 100)}%`);
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Mondays of the last 8 complete weeks, newest first. */
function lastWeeks() {
  const monday = new Date();
  monday.setHours(0, 0, 0, 0);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7) - 7);
  return Array.from({ length: 8 }, (_, i) => {
    const start = new Date(monday);
    start.setDate(start.getDate() - 7 * i);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    const f = (d) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
    return { value: isoDay(start), label: `${f(start)} – ${f(end)}` };
  });
}

/** Trend key "2026-10-12" or "2026-10-12T09" (site time) -> axis label. */
const keyLabel = (key) => (key.includes("T")
  ? `${key.slice(11)}:00`
  : new Date(`${key}T00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" }));

function Dashboard() {
  const { theme } = useTheme();
  // Recompute chart colours from the CSS tokens whenever the theme flips.
  const chart = useMemo(() => chartTheme(), [theme]); // eslint-disable-line react-hooks/exhaustive-deps
  const typeColor = { no_helmet: chart.helmet, no_vest: chart.vest, zone_intrusion: chart.intrusion };
  const health = useHealth();
  const toast = useToast();

  const [rangeKey, setRangeKey] = useState("7d");
  const range = RANGES.find((r) => r.value === rangeKey);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [weeks] = useState(lastWeeks);
  const [week, setWeek] = useState(weeks[0].value);
  const [exporting, setExporting] = useState(false);

  const requestId = useRef(0);

  // Effect-driven loads show skeletons; only the Refresh button shows a spinner.
  const load = useCallback(async () => {
    const id = ++requestId.current;
    const params = { bucket: range.value === "24h" ? "hour" : "day" };
    if (range.ms) params.date_from = new Date(Date.now() - range.ms).toISOString();
    try {
      const r = await API.get("/reports/summary", { params });
      if (id !== requestId.current) return; // a newer request (e.g. another range) won
      setData(r.data);
      setError("");
      setUpdatedAt(new Date());
    } catch (e) {
      if (id === requestId.current) setError(apiError(e, "Could not load dashboard data."));
    }
  }, [range]);

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

  const exportWeek = async () => {
    setExporting(true);
    try {
      await download("/reports/weekly", `safevision-week-${week}.html`, { week_start: week });
      toast("Weekly report downloaded. Open it in a browser to print or save as PDF.");
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setExporting(false);
    }
  };

  const trend = useMemo(() => (data ? data.trend.points.map((p) => ({
    label: keyLabel(p.key), ...Object.fromEntries(TYPE_OPTIONS.map((t) => [t.label, p[t.value]])),
  })) : []), [data]);

  const loading = !data && !error;
  const unavailable = !data && !!error; // failed load: never present that as "no violations"
  const fromDay = data?.date_from ? isoDay(new Date(data.date_from)) : "";
  const recordsLink = (extra = {}) => `/violations?${new URLSearchParams({ ...(fromDay && { from: fromDay }), ...extra })}`;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description={`PPE presence detection by zone, shift and type ${range.text}. Individual records and screenshots are one click deeper.`}
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
        <StatCard label="Awaiting review" icon={LuInbox} tone="tone-warning" loading={loading} value={data?.by_status.new ?? "—"} hint="Status: new" />
        <StatCard label="Helmet presence rate" icon={LuHardHat} tone="tone-ok" loading={loading} value={pct(data?.presence.helmet.rate)}
          hint={data ? `${data.presence.helmet.compliant} of ${data.presence.helmet.compliant + data.presence.helmet.violation} people seen` : "People seen with a helmet"} />
        <StatCard label="Vest presence rate" icon={LuShirt} tone="tone-ok" loading={loading} value={pct(data?.presence.vest.rate)}
          hint={data ? `${data.presence.vest.compliant} of ${data.presence.vest.compliant + data.presence.vest.violation} people seen` : "People seen with a vest"} />
      </div>

      {/* Trend + type */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <section className="card p-4 sm:p-5 lg:col-span-2 min-w-0" aria-label="Violations over time">
          <SectionTitle title="Violations over time" description={`By type, ${range.value === "24h" ? "per hour" : "per day"} (site time, ${data?.timezone ?? "…"})`} />
          {loading ? (
            <div className="skeleton h-[260px]" />
          ) : unavailable ? (
            <Unavailable />
          ) : !data.total ? (
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
                {TYPE_OPTIONS.map((t, i) => (
                  <Bar key={t.value} dataKey={t.label} stackId="v" fill={typeColor[t.value]} maxBarSize={36}
                    radius={i === TYPE_OPTIONS.length - 1 ? [4, 4, 0, 0] : undefined} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
          {!!data?.total && (
            <div className="flex flex-wrap gap-4 mt-3 text-xs text-muted">
              {TYPE_OPTIONS.map((t) => <Legend key={t.value} color={typeColor[t.value]} label={t.label} />)}
            </div>
          )}
        </section>

        <section className="card p-4 sm:p-5 min-w-0" aria-label="Violations by type">
          <SectionTitle title="By violation type" description={range.text} />
          {loading ? (
            <div className="skeleton h-[260px]" />
          ) : unavailable ? (
            <Unavailable />
          ) : !data.total ? (
            <EmptyState title="No data" className="h-[260px]">Nothing logged {range.text}.</EmptyState>
          ) : (
            <>
              <div className="relative">
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={TYPE_OPTIONS.map((t) => ({ name: t.label, value: data.by_type[t.value] }))}
                      dataKey="value" innerRadius={62} outerRadius={88} paddingAngle={2} stroke="none">
                      {TYPE_OPTIONS.map((t) => <Cell key={t.value} fill={typeColor[t.value]} />)}
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
                {TYPE_OPTIONS.map((t) => (
                  <div key={t.value} className="flex items-center justify-between">
                    <dt><Link to={recordsLink({ type: t.value })} className="hover:underline"><Legend color={typeColor[t.value]} label={t.label} /></Link></dt>
                    <dd className="tabular-nums text-fg">
                      {data.by_type[t.value]} <span className="text-muted">({Math.round((data.by_type[t.value] / data.total) * 100)}%)</span>
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </section>
      </div>

      {/* Zone and shift */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
        <section className="card min-w-0" aria-label="Violations by zone">
          <div className="p-4 sm:p-5 pb-0 sm:pb-0">
            <SectionTitle title="By zone" description="Select a zone to see its records" />
          </div>
          <AggregateTable
            loading={loading} unavailable={unavailable} empty={!data?.by_zone.length}
            head={["Camera / zone", "Helmet", "Vest", "Intrusion", "Total"]}
            rows={(data?.by_zone ?? []).map((g) => ({
              key: `${g.camera_id}-${g.zone_id}`,
              link: g.camera_id ? recordsLink({ camera_id: g.camera_id, ...(g.zone_id && { zone_id: g.zone_id }) }) : null,
              cells: [<span key="n"><span className="font-medium">{g.camera}</span>{g.zone && <span className="text-muted"> · {g.zone}</span>}</span>,
                ...TYPE_OPTIONS.map((t) => g[t.value]), <strong key="t">{g.total}</strong>],
            }))}
          />
        </section>

        <section className="card min-w-0" aria-label="Violations by shift">
          <div className="p-4 sm:p-5 pb-0 sm:pb-0">
            <SectionTitle title="By shift" description={`Presence rate = people seen with the item / people where it was decided`} />
          </div>
          <AggregateTable
            loading={loading} unavailable={unavailable} empty={!data?.by_shift.length}
            head={["Shift", "Violations", "Helmet presence", "Vest presence"]}
            rows={(data?.by_shift ?? []).map((s) => ({
              key: s.shift,
              cells: [<span key="s"><span className="font-medium">{s.shift}</span>{s.hours && <span className="text-muted text-xs"> {s.hours}</span>}</span>,
                s.total, pct(s.presence.helmet.rate), pct(s.presence.vest.rate)],
            }))}
          />
        </section>
      </div>

      {/* Review, causes, system */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
        <BreakdownCard
          title="Review status" loading={loading} unavailable={unavailable} total={data?.total}
          counts={data?.by_status} labels={Object.fromEntries(Object.entries(STATUS_META).map(([k, v]) => [k, v.label]))}
          action={<Link to="/violations?status=new" className="text-xs font-medium text-primary hover:underline">Review queue</Link>}
        />
        <BreakdownCard
          title="Causes recorded" loading={loading} unavailable={unavailable}
          total={data && Object.values(data.by_cause).reduce((a, b) => a + b, 0)}
          counts={data?.by_cause} labels={CAUSE_LABEL}
          note={data?.by_cause.ppe_not_issued ? `${data.by_cause.ppe_not_issued} record(s) where PPE was not issued: a supply gap for the site to fix.` : null}
        />
        <SystemCard health={health} />
      </div>

      {/* Weekly report + records */}
      <section className="card p-4 sm:p-5 mt-4 flex flex-col lg:flex-row lg:items-end gap-4" aria-label="Weekly report">
        <div className="flex-1 min-w-0">
          <SectionTitle title="Weekly report" description="Totals by zone, shift and type with presence rates and causes, compared with the week before. No images or individual records." />
          <div className="flex flex-wrap items-end gap-2">
            <label>
              <span className="label">Week (Monday to Sunday)</span>
              <select className="input w-auto" value={week} onChange={(e) => setWeek(e.target.value)}>
                {weeks.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
              </select>
            </label>
            <button className="btn btn-secondary" onClick={exportWeek} disabled={exporting}>
              {exporting ? <Spinner /> : <LuFileDown />} Download report
            </button>
          </div>
        </div>
        <Link to="/violations" className="btn btn-ghost">Individual records <LuArrowRight /></Link>
      </section>
    </div>
  );
}

function AggregateTable({ head, rows, loading, unavailable, empty }) {
  if (loading) return <div className="p-5 space-y-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-8" />)}</div>;
  if (unavailable) return <Unavailable h="" />;
  if (empty) return <p className="text-sm text-muted p-5 pt-3">No data in this period.</p>;
  return (
    <div className="overflow-x-auto mt-3">
      <table className="table">
        <thead><tr>{head.map((h, i) => <th key={h} className={i ? "text-right" : ""}>{h}</th>)}<th><span className="sr-only">Open</span></th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              {r.cells.map((c, i) => <td key={i} className={i ? "text-right tabular-nums" : "min-w-40"}>{c}</td>)}
              <td className="text-right w-px">
                {r.link && <Link to={r.link} className="btn btn-ghost btn-sm btn-icon" aria-label="Open records"><LuArrowRight /></Link>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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

function BreakdownCard({ title, counts, labels, total, loading, unavailable, action, note }) {
  return (
    <section className="card p-4 sm:p-5 min-w-0" aria-label={title}>
      <SectionTitle title={title} description="Share of records in range" action={action} />
      {loading ? (
        <div className="space-y-4">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-6" />)}</div>
      ) : unavailable || !total ? (
        <p className="text-sm text-muted py-6 text-center">{unavailable ? "Data unavailable." : "No data in this period."}</p>
      ) : (
        <>
          <ul className="space-y-3.5">
            {Object.entries(labels).map(([key, label]) => {
              const n = counts?.[key] || 0;
              const share = Math.round((n / total) * 100);
              return (
                <li key={key}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-fg">{label}</span>
                    <span className="tabular-nums text-muted">{n} · {share}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                    <div className="h-full rounded-full bg-primary/70" style={{ width: `${share}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
          {note && <p className="mt-4 text-xs text-muted">{note}</p>}
        </>
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
