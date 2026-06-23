import { useEffect, useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";
import { ThemeContext } from "../context/ThemeContext";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend
} from "recharts";

import {
  FaExclamationTriangle,
  FaHardHat,
  FaVest,
  FaCheckCircle
} from "react-icons/fa";

function Dashboard() {
  const { darkMode } = useContext(ThemeContext);
  const navigate = useNavigate();

  const [stats, setStats] = useState({
    total_violations: 0,
    no_vest_cases: 0,
    no_helmet_cases: 0,
    system_status: "Loading..."
  });

  const [recentViolations, setRecentViolations] =
    useState([]);
  const [allViolations, setAllViolations] = useState([]);
  const [chartView, setChartView] = useState("daily");

  const [loading, setLoading] = useState(true);

  useEffect(() => {

  const loadDashboard = async () => {
    try {
      const statsResponse =
        await API.get("/dashboard-stats");

      setStats(statsResponse.data);

      const violationsResponse =
        await API.get("/violations");

      setAllViolations(violationsResponse.data.violations);
      setRecentViolations(
        [...violationsResponse.data.violations]
          .slice(-5)
          .reverse()
      );

    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  loadDashboard();

  const interval = setInterval(
    loadDashboard,
    10000
  );

  return () => clearInterval(interval);

}, []);

  const distributionData = [
    {
      name: "No Vest",
      value: stats.no_vest_cases
    },
    {
      name: "No Helmet",
      value: stats.no_helmet_cases
    }
  ];

  const COLORS = [
    "#facc15",
    "#f97316"
  ];

  const getComparisonChartData = () => {
    if (!allViolations || allViolations.length === 0) return [];

    const groupedData = {};

    allViolations.forEach(v => {
      const datePart = v.timestamp.split('_')[0];
      const dateObj = new Date(datePart);
      let key;
      let sortTime;

      if (chartView === "weekly") {
        const day = dateObj.getDay();
        const diff = dateObj.getDate() - day + (day === 0 ? -6 : 1);
        const weekStart = new Date(new Date(dateObj).setDate(diff));
        key = `Week of ${weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
        sortTime = weekStart.getTime();
      } else {
        key = dateObj.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
        sortTime = dateObj.getTime();
      }

      if (!groupedData[key]) {
        groupedData[key] = { name: key, "No Vest": 0, "No Helmet": 0, sortTime };
      }

      if (v.violation_type === "Safety Vest Missing") {
         groupedData[key]["No Vest"] += 1;
      } else if (v.violation_type === "Helmet Missing") {
         groupedData[key]["No Helmet"] += 1;
      }
    });

    return Object.values(groupedData)
      .sort((a, b) => a.sortTime - b.sortTime)
      .slice(-7);
  };

  const comparisonChartData = getComparisonChartData();

  const getImageUrl = (path) => {
    if (!path) return "";
    const filename = path.split(/[/\\]/).pop();
    return `http://127.0.0.1:8000/screenshots/${filename}`;
  };

  const handleImageClick = (violationId) => {
    navigate(`/violations?highlight=${violationId}`);
  };

  return (
    <div>
      <h2 className="text-4xl font-bold mb-8">
        Dashboard Overview
      </h2>

      {loading ? (
        <p>Loading dashboard...</p>
      ) : (
        <>
          {/* Premium Cards */}

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">

            <div className="bg-gradient-to-r from-red-500 to-red-600 text-white p-6 rounded-2xl shadow-lg">
              <div className="flex justify-between items-center">
                <div>
                  <p>Total Violations</p>
                  <h2 className="text-5xl font-bold mt-2">
                    {stats.total_violations}
                  </h2>
                </div>

                <FaExclamationTriangle className="text-5xl opacity-70" />
              </div>
            </div>

            <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 text-white p-6 rounded-2xl shadow-lg">
              <div className="flex justify-between items-center">
                <div>
                  <p>No Vest Cases</p>
                  <h2 className="text-5xl font-bold mt-2">
                    {stats.no_vest_cases}
                  </h2>
                </div>

                <FaVest className="text-5xl opacity-70" />
              </div>
            </div>

            <div className="bg-gradient-to-r from-orange-500 to-orange-600 text-white p-6 rounded-2xl shadow-lg">
              <div className="flex justify-between items-center">
                <div>
                  <p>No Helmet Cases</p>
                  <h2 className="text-5xl font-bold mt-2">
                    {stats.no_helmet_cases}
                  </h2>
                </div>

                <FaHardHat className="text-5xl opacity-70" />
              </div>
            </div>

            <div className="bg-gradient-to-r from-green-500 to-green-600 text-white p-6 rounded-2xl shadow-lg">
              <div className="flex justify-between items-center">
                <div>
                  <p>System Status</p>
                  <h2 className="text-3xl font-bold mt-3">
                    {stats.system_status}
                  </h2>
                </div>

                <FaCheckCircle className="text-5xl opacity-70" />
              </div>
            </div>

          </div>

          {/* Charts */}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">

            <div className="bg-white dark:bg-slate-800 p-6 rounded-2xl shadow-lg">

              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center mb-4 gap-4">
                <h3 className="text-2xl font-bold text-black dark:text-white">
                  Violation Comparison
                </h3>
                <div className="flex bg-gray-100 dark:bg-slate-700 rounded-lg p-1 w-max">
                  <button
                    onClick={() => setChartView("daily")}
                    className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all duration-200 ${chartView === "daily" ? "bg-white dark:bg-slate-800 text-black dark:text-white shadow-sm" : "text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white"}`}
                  >
                    Daily
                  </button>
                  <button
                    onClick={() => setChartView("weekly")}
                    className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all duration-200 ${chartView === "weekly" ? "bg-white dark:bg-slate-800 text-black dark:text-white shadow-sm" : "text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white"}`}
                  >
                    Weekly
                  </button>
                </div>
              </div>

              <ResponsiveContainer width="100%" height={320}>
  <BarChart data={comparisonChartData}>

    <XAxis
      dataKey="name"
      tick={{ fill: darkMode ? "#cbd5e1" : "#475569", fontSize: 12 }}
    />

    <YAxis
      tick={{ fill: darkMode ? "#cbd5e1" : "#475569" }}
    />

    <Tooltip
  contentStyle={{
    backgroundColor: darkMode ? "#1e293b" : "#ffffff",
    border: darkMode ? "none" : "1px solid #e2e8f0",
    color: darkMode ? "white" : "black",
    borderRadius: "8px",
    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)"
  }}
/>
    <Legend wrapperStyle={{ color: darkMode ? "#cbd5e1" : "#475569", paddingTop: "10px" }} />

    <Bar
      dataKey="No Vest"
      fill="#facc15"
      radius={[4, 4, 0, 0]}
    />
    <Bar
      dataKey="No Helmet"
      fill="#f97316"
      radius={[4, 4, 0, 0]}
    />

  </BarChart>
</ResponsiveContainer>

            </div>

            <div className="bg-white dark:bg-slate-800 p-6 rounded-2xl shadow-lg">

  <h3 className="text-2xl font-bold mb-4 text-black dark:text-white">
    Violation Distribution
  </h3>

              <ResponsiveContainer width="100%" height={320}>
                <PieChart>

                  <Pie
                    data={distributionData}
                    dataKey="value"
                    outerRadius={110}
                    label
                  >
                    {distributionData.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={COLORS[index]}
                      />
                    ))}
                  </Pie>

                  <Tooltip />
                  <Legend  wrapperStyle={{
    color: darkMode ? "#ffffff" : "#000000"
  }}/>

                </PieChart>
              </ResponsiveContainer>

            </div>

          </div>

         {/* System Summary */}

<div className="bg-white dark:bg-slate-800 mt-8 p-6 rounded-2xl shadow-lg">

  <h3 className="text-2xl font-bold mb-5 text-black dark:text-white">
    System Summary
  </h3>

  <div className="grid md:grid-cols-2 gap-4">

    <div className="bg-gray-50 dark:bg-slate-700 p-4 rounded-xl">
      <p className="text-gray-600 dark:text-gray-300">
        Total Violations
      </p>

      <p className="text-3xl font-bold text-red-500">
        {stats.total_violations}
      </p>
    </div>

    <div className="bg-gray-50 dark:bg-slate-700 p-4 rounded-xl">
      <p className="text-gray-600 dark:text-gray-300">
        Vest Violations
      </p>

      <p className="text-3xl font-bold text-yellow-500">
        {stats.no_vest_cases}
      </p>
    </div>

    <div className="bg-gray-50 dark:bg-slate-700 p-4 rounded-xl">
      <p className="text-gray-600 dark:text-gray-300">
        Helmet Violations
      </p>

      <p className="text-3xl font-bold text-orange-500">
        {stats.no_helmet_cases}
      </p>
    </div>

    <div className="bg-gray-50 dark:bg-slate-700 p-4 rounded-xl">
      <p className="text-gray-600 dark:text-gray-300">
        Backend Status
      </p>

      <p className="text-3xl font-bold text-green-500">
        {stats.system_status}
      </p>
    </div>

  </div>

</div>

{/* Recent Violations */}

<div className="bg-white dark:bg-slate-800 mt-8 p-6 rounded-2xl shadow-lg">

  <h3 className="text-2xl font-bold mb-5 text-black dark:text-white">
    Recent Violations
  </h3>

  {recentViolations.length === 0 ? (
    <p className="text-black dark:text-white">
      No violations found.
    </p>
  ) : (
    <div className="overflow-x-auto">

      <table className="w-full text-black dark:text-white">

        <thead>
          <tr className="border-b dark:border-slate-700">

            <th className="text-left p-3">
              Image
            </th>

            <th className="text-left p-3">
              Type
            </th>

            <th className="text-left p-3">
              Severity
            </th>

            <th className="text-left p-3">
              Confidence
            </th>

            <th className="text-left p-3">
              Timestamp
            </th>

          </tr>
        </thead>

        <tbody>

          {recentViolations.map((item) => (
            <tr
              key={item.violation_id}
              className="border-b dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700"
            >

              <td className="p-3">
                {item.screenshot_path ? (
                  <img
                    src={getImageUrl(item.screenshot_path)}
                    alt="Violation"
                    className="w-16 h-10 object-cover rounded cursor-pointer hover:scale-110 transition"
                    onClick={() => handleImageClick(item.violation_id)}
                    title="Click to view details"
                  />
                ) : (
                  <span className="text-sm text-gray-500">N/A</span>
                )}
              </td>

              <td className="p-3">
                {item.violation_type}
              </td>

              <td className="p-3">
                <span
                  className={`px-3 py-1 rounded-full text-white ${
                    item.severity === "Critical"
                      ? "bg-purple-600"
                      : item.severity === "High"
                      ? "bg-red-500"
                      : "bg-yellow-500"
                  }`}
                >
                  {item.severity}
                </span>
              </td>

              <td className="p-3">
                {(
                  parseFloat(item.confidence) * 100
                ).toFixed(1)}
                %
              </td>

              <td className="p-3">
                {item.timestamp}
              </td>

            </tr>
          ))}

        </tbody>

      </table>

    </div>
  )}

</div>

        </>
      )}
    </div>
  );
}

export default Dashboard;