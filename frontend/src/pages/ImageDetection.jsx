import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LuScanLine, LuRefreshCw, LuTrash2, LuArrowRight, LuImage } from "react-icons/lu";
import API, { apiError, MAX_UPLOAD_MB } from "../services/api";
import { formatBytes, verdictFor } from "../services/detection";
import { DETECTION_CLASSES } from "../theme";
import { PageHeader, SectionTitle, Dropzone, Alert, ProgressBar, Spinner } from "../components/ui";
import DetectionOverlay from "../components/DetectionOverlay";

const ACCEPT = ".jpg,.jpeg,.png";

const STEPS = [
  "Upload a JPG or PNG photo of the work area.",
  "Three YOLOv8 models detect people, hard hats and high-visibility vests.",
  "Missing PPE counts as a violation only when it belongs to a detected person. A helmet held in the hand counts as missing.",
  "Violations are saved with the image as evidence for review.",
];

function ImageDetection() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [dims, setDims] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showBoxes, setShowBoxes] = useState(true);
  const replaceRef = useRef(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const choose = (f) => {
    setError("");
    if (!/\.(jpe?g|png)$/i.test(f.name)) return setError("Unsupported file type. Choose a JPG or PNG image.");
    if (f.size > MAX_UPLOAD_MB * 1024 * 1024) return setError(`The image is larger than ${MAX_UPLOAD_MB} MB.`);
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setDims(null);
    setResult(null);
  };

  const reset = () => { setFile(null); setPreview(null); setResult(null); setError(""); setDims(null); };

  const detect = async () => {
    if (!file || loading) return; // no duplicate submissions
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("image", file);
      const r = await API.post("/detect-image", form);
      setResult(r.data);
    } catch (e) {
      setError(apiError(e, "Detection failed."));
    } finally {
      setLoading(false);
    }
  };

  const verdict = result && verdictFor(result.summary);
  const loggedViolations = result ? result.summary.no_helmet + result.summary.no_vest : 0;

  return (
    <div>
      <PageHeader
        title="Image Detection"
        description="Check a photo for missing hard hats and high-visibility vests."
        actions={result && <button className="btn btn-secondary" onClick={reset}><LuImage /> Analyze another image</button>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Input */}
        <section className="card p-4 sm:p-5 lg:col-span-3 min-w-0" aria-label="Image input">
          <SectionTitle title="Input image" description={`JPG or PNG, up to ${MAX_UPLOAD_MB} MB`} />

          {!file ? (
            <Dropzone accept={ACCEPT} onFile={choose} title="Drop an image here, or browse" hint={`JPG · PNG · max ${MAX_UPLOAD_MB} MB`} />
          ) : (
            <>
              <div className="rounded-lg bg-canvas border border-line flex items-center justify-center overflow-hidden">
                <div className="relative inline-block max-w-full">
                  <img
                    src={preview}
                    alt={`Selected upload ${file.name}`}
                    onLoad={(e) => setDims({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
                    className={`block max-w-full max-h-[520px] ${loading ? "opacity-60" : ""}`}
                  />
                  {result && showBoxes && <DetectionOverlay detections={result.detections} width={dims?.w} height={dims?.h} />}
                  {loading && (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="badge tone-ok bg-surface h-8 px-3 text-sm"><Spinner /> Analyzing…</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate" title={file.name}>{file.name}</p>
                  <p className="text-xs text-muted tabular-nums">
                    {formatBytes(file.size)}{dims && ` · ${dims.w} × ${dims.h}px`}
                  </p>
                </div>
                {result && (
                  <label className="inline-flex items-center gap-2 text-sm text-muted cursor-pointer">
                    <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} className="accent-[var(--primary)] w-4 h-4" />
                    Show boxes
                  </label>
                )}
                <div className="flex gap-2">
                  <button className="btn btn-ghost btn-sm" onClick={() => replaceRef.current?.click()} disabled={loading}>
                    <LuRefreshCw /> Replace
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={reset} disabled={loading}>
                    <LuTrash2 /> Remove
                  </button>
                  <input ref={replaceRef} type="file" accept={ACCEPT} className="sr-only" tabIndex={-1}
                    onChange={(e) => { if (e.target.files[0]) choose(e.target.files[0]); e.target.value = ""; }} />
                </div>
              </div>

              {!result && (
                <button className="btn btn-primary btn-lg w-full mt-4" onClick={detect} disabled={loading}>
                  {loading ? <><Spinner /> Running detection…</> : <><LuScanLine /> Run detection</>}
                </button>
              )}
            </>
          )}

          {error && <Alert className="mt-4" onRetry={file && !result ? detect : undefined} onClose={() => setError("")}>{error}</Alert>}
        </section>

        {/* Results */}
        <section className="card p-4 sm:p-5 lg:col-span-2 min-w-0" aria-label="Detection results" aria-live="polite">
          <SectionTitle title="Results" description={result ? `${result.detections.length} objects detected` : "Findings appear here after a run"} />

          {loading ? (
            <div className="space-y-4">
              <p className="text-sm text-muted">Running the PPE, hard-hat and person models…</p>
              <ProgressBar value={null} label="Running detection" />
              <div className="grid grid-cols-2 gap-3">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-16" />)}</div>
            </div>
          ) : !result ? (
            <ol className="space-y-4">
              {STEPS.map((s, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="w-6 h-6 rounded-full bg-surface-2 border border-line text-xs font-semibold flex items-center justify-center flex-shrink-0 tabular-nums">{i + 1}</span>
                  <span className="text-muted pt-0.5">{s}</span>
                </li>
              ))}
            </ol>
          ) : (
            <div className="space-y-5">
              <Alert tone={verdict.tone} title={verdict.title}>{verdict.text}</Alert>
              <SummaryGrid summary={result.summary} />

              <div>
                <h3 className="text-xs font-medium text-muted mb-2">Detections</h3>
                {result.detections.length === 0 ? (
                  <p className="text-sm text-muted">Nothing was detected in this image.</p>
                ) : (
                  <ul className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {[...result.detections].sort((a, b) => b.confidence - a.confidence).map((d, i) => {
                      const meta = DETECTION_CLASSES[d.class_id];
                      return (
                        <li key={i} className="flex items-center gap-3 text-sm">
                          <span className={`badge ${meta.tone} w-28 justify-center`}>{meta.label}</span>
                          <div className="flex-1 h-1.5 rounded-full bg-surface-2 overflow-hidden">
                            <div className={`${meta.tone} h-full rounded-full`} style={{ width: `${d.confidence * 100}%`, background: "var(--tone)" }} />
                          </div>
                          <span className="tabular-nums text-muted w-12 text-right">{(d.confidence * 100).toFixed(0)}%</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              {loggedViolations > 0 && (
                <Link to="/violations?source=image" className="btn btn-secondary w-full">
                  Review in Violations <LuArrowRight />
                </Link>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export function SummaryGrid({ summary }) {
  return (
    <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-2 gap-2.5">
      {[
        ["Workers detected", summary.total_persons, "tone-info"],
        ["Hard hat worn", summary.helmet_worn, "tone-ok"],
        ["No hard hat", summary.no_helmet, "tone-danger"],
        ["Vest worn", summary.vest_worn, "tone-ok"],
        ["No vest", summary.no_vest, "tone-warning"],
      ].map(([label, n, tone]) => (
        <div key={label} className="rounded-lg border border-line bg-surface-2/50 px-3 py-2.5">
          <dt className="text-xs text-muted">{label}</dt>
          <dd className={`${tone} text-xl font-semibold tabular-nums mt-0.5`} style={{ color: n ? "var(--tone)" : undefined }}>{n}</dd>
        </div>
      ))}
    </dl>
  );
}

export default ImageDetection;
