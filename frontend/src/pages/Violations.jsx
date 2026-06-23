import { useEffect, useState, useRef } from "react";
import { useLocation, Link } from "react-router-dom";
import API from "../services/api";

function Violations() {
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);

  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const highlightId = queryParams.get("highlight");
  const rowRefs = useRef({});
  const [hasScrolled, setHasScrolled] = useState(false);

  useEffect(() => {
    let timeoutId;
    if (!loading && highlightId && rowRefs.current[highlightId] && !hasScrolled) {
      timeoutId = setTimeout(() => {
        if (rowRefs.current[highlightId]) {
          rowRefs.current[highlightId].scrollIntoView({ behavior: 'smooth', block: 'center' });
          setHasScrolled(true);
        }
      }, 300);
    }
    return () => clearTimeout(timeoutId);
  }, [loading, highlightId, violations, hasScrolled]);

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

    const interval = setInterval(
      loadViolations,
      10000
    );

    return () => clearInterval(interval);
  }, []);

  const getImageUrl = (path) => {
    const filename = path.split("\\").pop();
    return `http://127.0.0.1:8000/screenshots/${filename}`;
  };

  const downloadCSV = () => {
    window.open(
      "http://127.0.0.1:8000/download-violations",
      "_blank"
    );
  };

return (
  <div>
    <div className="mb-4">
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-2 text-blue-600 dark:text-blue-400 hover:underline font-semibold"
      >
        ← Go Back to Dashboard
      </Link>
    </div>
    <h1 className="text-3xl font-bold mb-6 text-black dark:text-white">
      Violations Monitoring
    </h1>

    <div className="bg-white dark:bg-slate-800 text-black dark:text-white rounded-xl shadow p-6">

      <div className="flex justify-between items-center mb-4">

        <h2 className="text-xl font-semibold">
          Recent Safety Violations
        </h2>

        <button
          onClick={downloadCSV}
          className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition"
        >
          Export CSV
        </button>

      </div>
        {loading ? (
          <p className="text-black dark:text-white">
            Loading violations...
          </p>
        ) : (
          <div className="overflow-x-auto">

            <table className="w-full border-collapse">

              <thead>

                <tr className="bg-gray-100 dark:bg-slate-700">

                  <th className="border p-3 text-left text-black dark:text-white">
                    ID
                  </th>

                  <th className="border p-3 text-left text-black dark:text-white">
                    Violation Type
                  </th>

                  <th className="border p-3 text-left text-black dark:text-white">
                    Severity
                  </th>

                  <th className="border p-3 text-left text-black dark:text-white">
                    Confidence
                  </th>

                  <th className="border p-3 text-left text-black dark:text-white">
                    Screenshot
                  </th>

                  <th className="border p-3 text-left text-black dark:text-white">
                    Timestamp
                  </th>

                </tr>

              </thead>

              <tbody>

                {violations.map((item) => {
                  const isHighlighted = item.violation_id === highlightId;
                  return (
                  <tr
                    key={item.violation_id}
                    ref={(el) => (rowRefs.current[item.violation_id] = el)}
                    className={`transition-all duration-700 ${
                      isHighlighted
                        ? "bg-yellow-200 dark:bg-yellow-900/50 shadow-inner"
                        : "hover:bg-gray-50 dark:hover:bg-slate-700"
                    }`}
                  >

                    <td className="border p-3 text-black dark:text-white">
                      {item.violation_id}
                    </td>

                    <td className="border p-3 text-black dark:text-white">
                      {item.violation_type}
                    </td>

                    <td className="border p-3 text-black dark:text-white">

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

                    <td className="border p-3 text-black dark:text-white">
                      {(parseFloat(item.confidence) * 100).toFixed(1)}%
                    </td>

                    <td className="border p-3 text-black dark:text-white">

                      {item.screenshot_path ? (
                        <div
                          onClick={() =>
                            setSelectedImage(
                              getImageUrl(
                                item.screenshot_path
                              )
                            )
                          }
                          className="cursor-pointer"
                        >

                          <img
                            src={getImageUrl(
                              item.screenshot_path
                            )}
                            alt="violation"
                            className="w-24 h-16 object-cover rounded border hover:scale-110 transition"
                          />

                        </div>
                      ) : (
                        <span>No Image</span>
                      )}

                    </td>

                    <td className="border p-3 text-black dark:text-white">
                      {item.timestamp}
                    </td>

                  </tr>
                )})}

              </tbody>

            </table>

            {violations.length === 0 && (
              <div className="text-center py-8 text-black dark:text-white">
                No violations found.
              </div>
            )}

          </div>
        )}

      </div>

      {selectedImage && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
          onClick={() => setSelectedImage(null)}
        >
          <img
            src={selectedImage}
            alt="Violation"
            className="max-w-[90%] max-h-[90%] rounded-xl shadow-2xl"
          />
        </div>
      )}

    </div>
  );
}

export default Violations;