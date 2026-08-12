import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { FaExclamationTriangle, FaHardHat, FaVest, FaCheckCircle } from "react-icons/fa";
import { useTheme } from "../context/ThemeContext";
import { CHART_COLORS, chartStyles, SEVERITY_STYLES } from "../theme";

const STAT_CARDS = [
  { key: "total_violations", label: "Total Violations", icon: <FaExclamationTriangle />, tone: "tone-alert" },
  { key: "no_vest_cases",    label: "No Vest Cases",    icon: <FaVest />,                tone: "tone-gold"  },
  { key: "no_helmet_cases",  label: "No Helmet Cases",  icon: <FaHardHat />,             tone: "tone-gold"  },
  { key: "system_status",    label: "System Status",    icon: <FaCheckCircle />,         tone: "tone-ok"    },
];

function Dashboard() {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const chart = useMemo(() => chartStyles(theme), [theme]);

  const [stats, setStats] = useState({ total_violations: 0, no_vest_cases: 0, no_helmet_cases: 0, system_status: "Loading…" });
  const [recentViolations, setRecentViolations] = useState([]);
  const [allViolations, setAllViolations] = useState([]);
  const [chartView, setChartView] = useState("daily");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [statsRes, violRes] = await Promise.all([
          API.get("/dashboard-stats"),
          API.get("/violations"),
        ]);
        setStats(statsRes.data);
        setAllViolations(violRes.data.violations);
        setRecentViolations([...violRes.data.violations].slice(-5).reverse());
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, []);

  const distributionData = [
    { name: "No Vest",   value: stats.no_vest_cases   },
    { name: "No Helmet", value: stats.no_helmet_cases },
  ];

  const getChartData = () => {
    if (!allViolations?.length) return [];
    const grouped = {};
    allViolations.forEach((v) => {
      const dateObj = new Date(v.timestamp.split("_")[0]);
      let key, sortTime;
      if (chartView === "weekly") {
        const day = dateObj.getDay();
        const diff = dateObj.getDate() - day + (day === 0 ? -6 : 1);
        const weekStart = new Date(new Date(dateObj).setDate(diff));
        key = `Week of ${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
        sortTime = weekStart.getTime();
      } else {
        key = dateObj.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
        sortTime = dateObj.getTime();
      }
      if (!grouped[key]) grouped[key] = { name: key, "No Vest": 0, "No Helmet": 0, sortTime };
      if (v.violation_type === "Safety Vest Missing") grouped[key]["No Vest"] += 1;
      else if (v.violation_type === "Helmet Missing") grouped[key]["No Helmet"] += 1;
    });
    return Object.values(grouped).sort((a, b) => a.sortTime - b.sortTime).slice(-7);
  };

  const chartData = getChartData();

  const getImageUrl = (path) => {
    const filename = path.split(/[/\\]/).pop();
    return `http://127.0.0.1:8000/screenshots/${filename}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="sv-fg-muted flex items-center gap-3 text-sm">
          <span
            className="sv-ink-gold w-2 h-2 rounded-full bg-current"
            style={{ animation: "sv-blink 1.2s ease-in-out infinite" }}
          />
          Loading dashboard…
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {STAT_CARDS.map((card) => (
          <div key={card.key} className={`${card.tone} sv-tone rounded-2xl p-6`}>
            <div className="flex items-start justify-between">
              <div>
                <p className="sv-mono sv-fg-muted text-[9.5px] font-bold uppercase tracking-[0.16em] mb-2.5">
                  {card.label}
                </p>
                <p className="sv-tone-ink text-4xl font-extrabold tracking-tight">
                  {stats[card.key]}
                </p>
              </div>
              <div className="sv-tone-ink text-3xl opacity-45">{card.icon}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Bar chart */}
        <div className="sv-panel rounded-2xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <h3 className="sv-fg text-lg font-bold">Violation Comparison</h3>
            <div className="sv-panel-sub flex rounded-lg p-1 w-max">
              {["daily", "weekly"].map((v) => (
                <button
                  key={v}
                  onClick={() => setChartView(v)}
                  className={`px-4 py-1.5 rounded-md text-xs font-bold capitalize transition-all ${
                    chartView === v
                      ? "sv-gold-btn text-[var(--sv-on-accent)]"
                      : "sv-linkish"
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={chart.axis} axisLine={false} tickLine={false} />
              <YAxis tick={chart.axis} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={chart.tooltip} cursor={chart.cursor} />
              <Legend wrapperStyle={chart.legend} />
              <Bar dataKey="No Vest"   fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
              <Bar dataKey="No Helmet" fill={CHART_COLORS[1]} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie chart */}
        <div className="sv-panel rounded-2xl p-6">
          <h3 className="sv-fg text-lg font-bold mb-6">Violation Distribution</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={distributionData} dataKey="value" outerRadius={100} innerRadius={50} paddingAngle={4} label>
                {distributionData.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i]} stroke={chart.cellStroke} strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip contentStyle={chart.tooltip} />
              <Legend wrapperStyle={chart.legend} />
            </PieChart>
          </ResponsiveContainer>
        </div>

      </div>

      {/* System Summary */}
      <div className="sv-panel rounded-2xl p-6">
        <h3 className="sv-fg text-lg font-bold mb-5">System Summary</h3>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Total Violations",  val: stats.total_violations, tone: "tone-alert" },
            { label: "Vest Violations",   val: stats.no_vest_cases,    tone: "tone-gold"  },
            { label: "Helmet Violations", val: stats.no_helmet_cases,  tone: "tone-gold"  },
            { label: "Backend Status",    val: stats.system_status,    tone: "tone-ok"    },
          ].map((item) => (
            <div key={item.label} className={`${item.tone} sv-panel-sub rounded-xl p-4`}>
              <p className="sv-mono sv-fg-muted text-[9px] font-bold uppercase tracking-[0.14em] mb-2">
                {item.label}
              </p>
              <p className="sv-tone-ink text-2xl font-extrabold">{item.val}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Violations */}
      <div className="sv-panel rounded-2xl p-6">
        <h3 className="sv-fg text-lg font-bold mb-5">Recent Violations</h3>

        {recentViolations.length === 0 ? (
          <div className="sv-fg-faint text-center py-12 text-sm">No violations recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="sv-bd-b">
                  {["Image", "Type", "Severity", "Confidence", "Timestamp"].map((h) => (
                    <th key={h} className="sv-mono sv-fg-muted text-left px-4 py-3 text-[9.5px] font-bold uppercase tracking-[0.14em]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentViolations.map((item) => (
                  <tr key={item.violation_id} className="sv-row transition-colors">
                    <td className="px-4 py-3">
                      {item.screenshot_path ? (
                        <img
                          src={getImageUrl(item.screenshot_path)}
                          alt="Violation"
                          className="sv-bd w-16 h-10 object-cover rounded-lg border cursor-pointer hover:scale-110 transition-transform"
                          onClick={() => navigate(`/violations?highlight=${item.violation_id}`)}
                        />
                      ) : (
                        <span className="sv-fg-faint text-xs">N/A</span>
                      )}
                    </td>
                    <td className="sv-fg px-4 py-3">{item.violation_type}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.Medium}`}>
                        {item.severity}
                      </span>
                    </td>
                    <td className="sv-fg px-4 py-3 tabular-nums">{(parseFloat(item.confidence) * 100).toFixed(1)}%</td>
                    <td className="sv-mono sv-fg-dim px-4 py-3 text-[11px]">{item.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}

export default Dashboard;
