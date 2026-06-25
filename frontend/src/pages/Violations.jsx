import { useEffect, useState, useRef } from "react";
import { useLocation, Link } from "react-router-dom";
import API from "../services/api";
import { FaDownload, FaArrowLeft, FaExclamationTriangle } from "react-icons/fa";

const SEVERITY_STYLES = {
  Critical: "bg-purple-500/20 text-purple-300 border border-purple-500/30",
  High:     "bg-red-500/20    text-red-300    border border-red-500/30",
  Medium:   "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30",
};

function Violations() {
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);

  const location = useLocation();
  const highlightId = new URLSearchParams(location.search).get("highlight");
  const rowRefs = useRef({});
  const hasScrolled = useRef(false);

  useEffect(() => {
    if (!loading && highlightId && rowRefs.current[highlightId] && !hasScrolled.current) {
      const t = setTimeout(() => {
        rowRefs.current[highlightId]?.scrollIntoView({ behavior: "smooth", block: "center" });
        hasScrolled.current = true;
      }, 300);
      return () => clearTimeout(t);
    }
  }, [loading, highlightId, violations]);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await API.get("/violations");
        setViolations(r.data.violations);
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

  const getImageUrl = (path) => {
    const filename = path.split(/[/\\]/).pop();
    return `http://127.0.0.1:8000/screenshots/${filename}`;
  };

  const downloadCSV = () => window.open("http://127.0.0.1:8000/download-violations", "_blank");

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link to="/dashboard" className="inline-flex items-center gap-2 text-slate-400 hover:text-white text-sm font-medium transition-colors mb-3">
            <FaArrowLeft className="text-xs" /> Back to Dashboard
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
              <FaExclamationTriangle />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Violations Monitor</h1>
              <p className="text-xs text-slate-400">{violations.length} total records</p>
            </div>
          </div>
        </div>

        <button
          onClick={downloadCSV}
          className="flex items-center gap-2 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 text-emerald-400 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all"
        >
          <FaDownload /> Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl overflow-hidden">

        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-500">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping mr-3" />
            Loading violations…
          </div>
        ) : violations.length === 0 ? (
          <div className="text-center py-16 text-slate-500">
            <FaExclamationTriangle className="text-3xl mx-auto mb-3 opacity-30" />
            No violations recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                  {["ID", "Violation Type", "Severity", "Confidence", "Screenshot", "Timestamp"].map((h) => (
                    <th key={h} className="text-left px-5 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {violations.map((item) => {
                  const isHl = item.violation_id === highlightId;
                  return (
                    <tr
                      key={item.violation_id}
                      ref={(el) => (rowRefs.current[item.violation_id] = el)}
                      className={`border-b border-white/[0.04] transition-all duration-500 ${
                        isHl
                          ? "bg-yellow-500/10 border-yellow-500/20"
                          : "hover:bg-white/[0.02]"
                      }`}
                    >
                      <td className="px-5 py-4 text-slate-500 text-xs font-mono">{item.violation_id}</td>
                      <td className="px-5 py-4 text-slate-300 font-medium whitespace-nowrap">{item.violation_type}</td>
                      <td className="px-5 py-4">
                        <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.Medium}`}>
                          {item.severity}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-slate-300">{(parseFloat(item.confidence) * 100).toFixed(1)}%</td>
                      <td className="px-5 py-4">
                        {item.screenshot_path ? (
                          <img
                            src={getImageUrl(item.screenshot_path)}
                            alt="violation"
                            className="w-20 h-14 object-cover rounded-lg border border-white/[0.08] cursor-pointer hover:scale-110 hover:shadow-xl transition-transform"
                            onClick={() => setSelectedImage(getImageUrl(item.screenshot_path))}
                          />
                        ) : (
                          <span className="text-slate-600 text-xs">No image</span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-slate-400 text-xs whitespace-nowrap">{item.timestamp}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Lightbox */}
      {selectedImage && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedImage(null)}
        >
          <img
            src={selectedImage}
            alt="Violation"
            className="max-w-[90vw] max-h-[85vh] rounded-2xl shadow-2xl border border-white/10"
          />
          <p className="absolute bottom-6 text-slate-400 text-sm">Click anywhere to close</p>
        </div>
      )}
    </div>
  );
}

export default Violations;
