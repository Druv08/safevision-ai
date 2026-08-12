import { useEffect, useState, useRef } from "react";
import { useLocation, Link } from "react-router-dom";
import API from "../services/api";
import { FaDownload, FaArrowLeft, FaExclamationTriangle } from "react-icons/fa";
import { SEVERITY_STYLES } from "../theme";

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
          <Link
            to="/dashboard"
            className="sv-linkish inline-flex items-center gap-2 text-sm font-medium mb-3"
          >
            <FaArrowLeft className="text-xs" /> Back to Dashboard
          </Link>
          <div className="flex items-center gap-3">
            <div className="tone-alert sv-tone sv-tone-ink w-10 h-10 rounded-xl flex items-center justify-center">
              <FaExclamationTriangle />
            </div>
            <div>
              <h1 className="sv-fg text-xl font-extrabold">Violations Monitor</h1>
              <p className="sv-mono sv-fg-muted text-[10px] font-bold uppercase tracking-[0.14em] mt-1">
                {violations.length} total records
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={downloadCSV}
          className="sv-gold-btn flex items-center gap-2 text-[var(--sv-on-accent)] px-5 py-2.5 rounded-xl font-bold text-sm transition-shadow duration-300"
        >
          <FaDownload /> Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="sv-panel rounded-2xl overflow-hidden">

        {loading ? (
          <div className="sv-fg-muted flex items-center justify-center py-16 text-sm">
            <span
              className="sv-ink-gold w-2 h-2 rounded-full bg-current mr-3"
              style={{ animation: "sv-blink 1.2s ease-in-out infinite" }}
            />
            Loading violations…
          </div>
        ) : violations.length === 0 ? (
          <div className="sv-fg-faint text-center py-16 text-sm">
            <FaExclamationTriangle className="text-3xl mx-auto mb-3 opacity-40" />
            No violations recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="sv-bd-b sv-panel-sub">
                  {["ID", "Violation Type", "Severity", "Confidence", "Screenshot", "Timestamp"].map((h) => (
                    <th
                      key={h}
                      className="sv-mono sv-fg-muted text-left px-5 py-4 text-[9.5px] font-bold uppercase tracking-[0.14em] whitespace-nowrap"
                    >
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
                      className={`sv-row transition-all duration-500 ${isHl ? "sv-row-highlight" : ""}`}
                    >
                      <td className="sv-mono sv-fg-faint px-5 py-4 text-[11px]">{item.violation_id}</td>
                      <td className="sv-fg px-5 py-4 font-medium whitespace-nowrap">{item.violation_type}</td>
                      <td className="px-5 py-4">
                        <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.Medium}`}>
                          {item.severity}
                        </span>
                      </td>
                      <td className="sv-fg px-5 py-4 tabular-nums">{(parseFloat(item.confidence) * 100).toFixed(1)}%</td>
                      <td className="px-5 py-4">
                        {item.screenshot_path ? (
                          <img
                            src={getImageUrl(item.screenshot_path)}
                            alt="violation"
                            className="sv-bd w-20 h-14 object-cover rounded-lg border cursor-pointer hover:scale-110 transition-transform"
                            onClick={() => setSelectedImage(getImageUrl(item.screenshot_path))}
                          />
                        ) : (
                          <span className="sv-fg-faint text-xs">No image</span>
                        )}
                      </td>
                      <td className="sv-mono sv-fg-dim px-5 py-4 text-[11px] whitespace-nowrap">{item.timestamp}</td>
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
          className="sv-lightbox fixed inset-0 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedImage(null)}
        >
          <img
            src={selectedImage}
            alt="Violation"
            className="sv-bd max-w-[90vw] max-h-[85vh] rounded-2xl shadow-2xl border"
          />
          <p className="sv-mono sv-fg-dim absolute bottom-6 text-[11px] uppercase tracking-[0.14em]">
            Click anywhere to close
          </p>
        </div>
      )}
    </div>
  );
}

export default Violations;
