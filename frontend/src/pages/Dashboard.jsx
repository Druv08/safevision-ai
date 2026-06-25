import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { FaExclamationTriangle, FaHardHat, FaVest, FaCheckCircle } from "react-icons/fa";

const STAT_CARDS = [
  { key: "total_violations", label: "Total Violations",  icon: <FaExclamationTriangle />, bg: "bg-red-500/10",    border: "border-red-500/20",    icon_c: "text-red-400",    val_c: "text-red-400"    },
  { key: "no_vest_cases",    label: "No Vest Cases",     icon: <FaVest />,                bg: "bg-yellow-500/10", border: "border-yellow-500/20", icon_c: "text-yellow-400", val_c: "text-yellow-400" },
  { key: "no_helmet_cases",  label: "No Helmet Cases",   icon: <FaHardHat />,             bg: "bg-orange-500/10", border: "border-orange-500/20", icon_c: "text-orange-400", val_c: "text-orange-400" },
  { key: "system_status",    label: "System Status",     icon: <FaCheckCircle />,         bg: "bg-green-500/10",  border: "border-green-500/20",  icon_c: "text-green-400",  val_c: "text-green-400"  },
];

const PIE_COLORS = ["#facc15", "#f97316"];

const TOOLTIP_STYLE = {
  backgroundColor: "#0f172a",
  border: "1px solid rgba(255,255,255,0.08)",
  color: "#e2e8f0",
  borderRadius: "12px",
  boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
};

const SEVERITY_COLORS = {
  Critical: "bg-purple-500/20 text-purple-300 border border-purple-500/30",
  High:     "bg-red-500/20    text-red-300    border border-red-500/30",
  Medium:   "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30",
};

function Dashboard() {
  const navigate = useNavigate();
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
        <div className="flex items-center gap-3 text-slate-400">
          <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping" />
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
          <div key={card.key} className={`${card.bg} border ${card.border} rounded-2xl p-6 backdrop-blur-sm`}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{card.label}</p>
                <p className={`text-4xl font-black ${card.val_c}`}>
                  {stats[card.key]}
                </p>
              </div>
              <div className={`text-3xl ${card.icon_c} opacity-60`}>{card.icon}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Bar chart */}
        <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <h3 className="text-lg font-bold text-white">Violation Comparison</h3>
            <div className="flex bg-white/[0.05] rounded-lg p-1 w-max border border-white/[0.08]">
              {["daily", "weekly"].map((v) => (
                <button
                  key={v}
                  onClick={() => setChartView(v)}
                  className={`px-4 py-1.5 rounded-md text-xs font-semibold capitalize transition-all ${
                    chartView === v
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Legend wrapperStyle={{ color: "#94a3b8", paddingTop: "12px", fontSize: "12px" }} />
              <Bar dataKey="No Vest"   fill="#facc15" radius={[4, 4, 0, 0]} />
              <Bar dataKey="No Helmet" fill="#f97316" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Pie chart */}
        <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl p-6">
          <h3 className="text-lg font-bold text-white mb-6">Violation Distribution</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={distributionData} dataKey="value" outerRadius={100} innerRadius={50} paddingAngle={4} label>
                {distributionData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i]} />
                ))}
              </Pie>
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ color: "#94a3b8", fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

      </div>

      {/* System Summary */}
      <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl p-6">
        <h3 className="text-lg font-bold text-white mb-5">System Summary</h3>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Total Violations",  val: stats.total_violations,  color: "text-red-400"    },
            { label: "Vest Violations",   val: stats.no_vest_cases,    color: "text-yellow-400" },
            { label: "Helmet Violations", val: stats.no_helmet_cases,  color: "text-orange-400" },
            { label: "Backend Status",    val: stats.system_status,    color: "text-green-400"  },
          ].map((item) => (
            <div key={item.label} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4">
              <p className="text-xs text-slate-400 font-medium mb-2">{item.label}</p>
              <p className={`text-2xl font-bold ${item.color}`}>{item.val}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Violations */}
      <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl p-6">
        <h3 className="text-lg font-bold text-white mb-5">Recent Violations</h3>

        {recentViolations.length === 0 ? (
          <div className="text-center py-12 text-slate-500">No violations recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  {["Image", "Type", "Severity", "Confidence", "Timestamp"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentViolations.map((item) => (
                  <tr key={item.violation_id} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      {item.screenshot_path ? (
                        <img
                          src={getImageUrl(item.screenshot_path)}
                          alt="Violation"
                          className="w-16 h-10 object-cover rounded-lg cursor-pointer hover:scale-110 hover:shadow-lg transition-transform"
                          onClick={() => navigate(`/violations?highlight=${item.violation_id}`)}
                        />
                      ) : (
                        <span className="text-slate-600 text-xs">N/A</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-300">{item.violation_type}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${SEVERITY_COLORS[item.severity] || SEVERITY_COLORS.Medium}`}>
                        {item.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{(parseFloat(item.confidence) * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{item.timestamp}</td>
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
