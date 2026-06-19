import { useEffect, useState } from "react";
import API from "../services/api";

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

function Dashboard() {
  const [stats, setStats] = useState({
    total_violations: 0,
    no_vest_cases: 0,
    no_helmet_cases: 0,
    system_status: "Loading..."
  });

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const response = await API.get(
          "/dashboard-stats"
        );

        setStats(response.data);
      } catch (error) {
        console.error(error);
        alert(
          "Failed to load dashboard stats."
        );
      } finally {
        setLoading(false);
      }
    };

    loadDashboard();
  }, []);

  const chartData = [
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

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">
        Dashboard Overview
      </h2>

      {loading ? (
        <p>Loading dashboard...</p>
      ) : (
        <>
          {/* Stats Cards */}

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">

            <div className="bg-white p-5 rounded-xl shadow">
              <h3 className="text-gray-500">
                Total Violations
              </h3>

              <p className="text-4xl font-bold text-red-500">
                {stats.total_violations}
              </p>
            </div>

            <div className="bg-white p-5 rounded-xl shadow">
              <h3 className="text-gray-500">
                No Vest Cases
              </h3>

              <p className="text-4xl font-bold text-yellow-500">
                {stats.no_vest_cases}
              </p>
            </div>

            <div className="bg-white p-5 rounded-xl shadow">
              <h3 className="text-gray-500">
                No Helmet Cases
              </h3>

              <p className="text-4xl font-bold text-orange-500">
                {stats.no_helmet_cases}
              </p>
            </div>

            <div className="bg-white p-5 rounded-xl shadow">
              <h3 className="text-gray-500">
                System Status
              </h3>

              <p className="text-3xl font-bold text-green-600">
                {stats.system_status}
              </p>
            </div>

          </div>

          {/* Charts */}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">

            {/* Bar Chart */}

            <div className="bg-white p-6 rounded-xl shadow">

              <h3 className="text-xl font-bold mb-4">
                Violation Comparison
              </h3>

              <ResponsiveContainer
                width="100%"
                height={300}
              >
                <BarChart data={chartData}>
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />

                  <Bar
                    dataKey="value"
                    fill="#3b82f6"
                  />
                </BarChart>
              </ResponsiveContainer>

            </div>

            {/* Pie Chart */}

            <div className="bg-white p-6 rounded-xl shadow">

              <h3 className="text-xl font-bold mb-4">
                Violation Distribution
              </h3>

              <ResponsiveContainer
                width="100%"
                height={300}
              >
                <PieChart>

                  <Pie
                    data={chartData}
                    dataKey="value"
                    outerRadius={100}
                    label
                  >
                    {chartData.map(
                      (entry, index) => (
                        <Cell
                          key={index}
                          fill={
                            COLORS[index]
                          }
                        />
                      )
                    )}
                  </Pie>

                  <Tooltip />
                  <Legend />

                </PieChart>
              </ResponsiveContainer>

            </div>

          </div>

          {/* Summary */}

          <div className="bg-white mt-8 p-6 rounded-xl shadow">

            <h3 className="text-2xl font-bold mb-4">
              System Summary
            </h3>

            <div className="space-y-2">

              <p>
                Total Violations Detected:
                <strong>
                  {" "}
                  {stats.total_violations}
                </strong>
              </p>

              <p>
                Safety Vest Violations:
                <strong>
                  {" "}
                  {stats.no_vest_cases}
                </strong>
              </p>

              <p>
                Helmet Violations:
                <strong>
                  {" "}
                  {stats.no_helmet_cases}
                </strong>
              </p>

              <p>
                Backend Status:
                <strong className="text-green-600">
                  {" "}
                  {stats.system_status}
                </strong>
              </p>

            </div>

          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;