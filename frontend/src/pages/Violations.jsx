import { useEffect, useState } from "react";
import API from "../services/api";

function Violations() {
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadViolations = async () => {
      try {
        const response = await API.get("/violations");

        setViolations(response.data.violations);
      } catch (error) {
        console.error(error);
        alert("Failed to load violations.");
      } finally {
        setLoading(false);
      }
    };

    loadViolations();
  }, []);

  const getImageUrl = (path) => {
    const filename = path.split("\\").pop();

    return `http://127.0.0.1:8000/screenshots/${filename}`;
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">
        Violations Monitoring
      </h1>

      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-xl font-semibold mb-4">
          Recent Safety Violations
        </h2>

        {loading ? (
          <p>Loading violations...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border p-3 text-left">
                    ID
                  </th>

                  <th className="border p-3 text-left">
                    Violation Type
                  </th>

                  <th className="border p-3 text-left">
                    Severity
                  </th>

                  <th className="border p-3 text-left">
                    Confidence
                  </th>

                  <th className="border p-3 text-left">
                    Screenshot
                  </th>

                  <th className="border p-3 text-left">
                    Timestamp
                  </th>
                </tr>
              </thead>

              <tbody>
                {violations.map((item) => (
                  <tr key={item.violation_id}>
                    <td className="border p-3">
                      {item.violation_id}
                    </td>

                    <td className="border p-3">
                      {item.violation_type}
                    </td>

                    <td className="border p-3">
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

                    <td className="border p-3">
                      {(
                        parseFloat(item.confidence) * 100
                      ).toFixed(1)}
                      %
                    </td>

                    <td className="border p-3">
                      {item.screenshot_path ? (
                        <a
                          href={getImageUrl(
                            item.screenshot_path
                          )}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <img
                            src={getImageUrl(
                              item.screenshot_path
                            )}
                            alt="violation"
                            className="w-24 h-16 object-cover rounded border hover:scale-105 transition"
                          />
                        </a>
                      ) : (
                        <span>No Image</span>
                      )}
                    </td>

                    <td className="border p-3">
                      {item.timestamp}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {violations.length === 0 && (
              <div className="text-center py-8">
                No violations found.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Violations;