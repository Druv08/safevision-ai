import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LuPlay, LuRefreshCw, LuTrash2, LuArrowRight, LuFilm, LuX, LuCircleCheck, LuTriangleAlert, LuClock } from "react-icons/lu";
import API, { apiError, MAX_UPLOAD_MB } from "../services/api";
import { formatBytes } from "../services/detection";
import { PageHeader, SectionTitle, Dropzone, Alert, ProgressBar, Spinner, EmptyState } from "../components/ui";

const ACCEPT = ".mp4,.mov,.avi,.webm";
const TYPE_LABEL = { no_helmet: "Helmet missing", no_vest: "Vest missing" };

const clock = (s) => {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
};

function VideoDetection() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [meta, setMeta] = useState(null); // { duration, w, h }
  const [phase, setPhase] = useState("idle"); // idle | uploading | processing | done
  const [progress, setProgress] = useState(0);
  const [startedAt, setStartedAt] = useState(null);
  const [now, setNow] = useState(() => Date.now());
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const videoRef = useRef(null);
  const replaceRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => () => abortRef.current?.abort(), []); // leaving the page stops the upload

  // Real elapsed time while the server works; the backend reports no progress for this step.
  useEffect(() => {
    if (phase !== "processing") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [phase]);

  const busy = phase === "uploading" || phase === "processing";

  const choose = (f) => {
    setError("");
    if (!/\.(mp4|mov|avi|webm)$/i.test(f.name)) return setError("Unsupported file type. Choose an MP4, MOV, AVI or WEBM video.");
    if (f.size > MAX_UPLOAD_MB * 1024 * 1024) return setError(`The video is larger than ${MAX_UPLOAD_MB} MB.`);
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setMeta(null);
    setResult(null);
    setPhase("idle");
  };

  const reset = () => { setFile(null); setPreview(null); setMeta(null); setResult(null); setError(""); setPhase("idle"); };

  const analyze = async () => {
    if (!file || busy) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setError("");
    setResult(null);
    setProgress(0);
    setPhase("uploading");
    try {
      const form = new FormData();
      form.append("video", file);
      const r = await API.post("/detect-video", form, {
        signal: controller.signal,
        onUploadProgress: (p) => {
          if (!p.total) return;
          const pct = Math.round((p.loaded / p.total) * 100);
          setProgress(pct);
          if (pct >= 100) { setStartedAt(Date.now()); setNow(Date.now()); setPhase("processing"); }
        },
      });
      setResult(r.data);
      setPhase("done");
    } catch (e) {
      setError(apiError(e, "Video analysis failed."));
      setPhase("idle");
    } finally {
      abortRef.current = null;
    }
  };

  const seek = (t) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = t;
    v.pause();
    v.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const elapsed = startedAt ? Math.max(0, Math.round((now - startedAt) / 1000)) : 0;

  return (
    <div>
      <PageHeader
        title="Video Detection"
        description="Analyze recorded footage frame by frame and log every PPE violation with a timestamp."
        actions={result && <button className="btn btn-secondary" onClick={reset}><LuFilm /> Analyze another video</button>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <section className="card p-4 sm:p-5 lg:col-span-3 min-w-0" aria-label="Video input">
          <SectionTitle title="Input video" description={`MP4, MOV, AVI or WEBM, up to ${MAX_UPLOAD_MB} MB`} />

          {!file ? (
            <Dropzone accept={ACCEPT} onFile={choose} title="Drop a video here, or browse" hint={`MP4 · MOV · AVI · WEBM · max ${MAX_UPLOAD_MB} MB`} />
          ) : (
            <>
              <div className="relative">
                <video
                  ref={videoRef}
                  src={preview}
                  controls
                  playsInline
                  onLoadedMetadata={(e) => {
                    const v = e.currentTarget;
                    setMeta({ duration: Number.isFinite(v.duration) ? v.duration : null, w: v.videoWidth, h: v.videoHeight, playable: v.videoWidth > 0 });
                  }}
                  onError={() => setMeta({ playable: false })}
                  className="w-full max-h-[460px] rounded-lg bg-black border border-line"
                />
                {meta?.playable === false && (
                  <div className="absolute inset-0 flex items-center justify-center p-4 pointer-events-none">
                    <p className="text-sm text-white/85 text-center max-w-sm bg-black/60 rounded-lg px-3 py-2">
                      This browser can't preview this video's codec. The server decodes it separately, so analysis still works.
                    </p>
                  </div>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate" title={file.name}>{file.name}</p>
                  <p className="text-xs text-muted tabular-nums">
                    {formatBytes(file.size)}
                    {meta?.duration != null && ` · ${clock(meta.duration)}`}
                    {meta?.w > 0 && ` · ${meta.w} × ${meta.h}px`}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button className="btn btn-ghost btn-sm" onClick={() => replaceRef.current?.click()} disabled={busy}><LuRefreshCw /> Replace</button>
                  <button className="btn btn-ghost btn-sm" onClick={reset} disabled={busy}><LuTrash2 /> Remove</button>
                  <input ref={replaceRef} type="file" accept={ACCEPT} className="sr-only" tabIndex={-1}
                    onChange={(e) => { if (e.target.files[0]) choose(e.target.files[0]); e.target.value = ""; }} />
                </div>
              </div>

              {phase === "idle" && (
                <button className="btn btn-primary btn-lg w-full mt-4" onClick={analyze}>
                  <LuPlay /> Analyze video
                </button>
              )}

              {phase === "uploading" && (
                <div className="mt-4 rounded-lg border border-line bg-surface-2/50 p-4 space-y-3" role="status">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">Uploading… <span className="tabular-nums text-muted">{progress}%</span></span>
                    <button className="btn btn-ghost btn-sm" onClick={() => abortRef.current?.abort()}><LuX /> Cancel</button>
                  </div>
                  <ProgressBar value={progress} label="Upload progress" />
                </div>
              )}

              {phase === "processing" && (
                <div className="mt-4 rounded-lg border border-line bg-surface-2/50 p-4 space-y-3" role="status">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium flex items-center gap-2"><Spinner className="text-primary" /> Analyzing every frame on the server</span>
                    <span className="tabular-nums text-muted flex items-center gap-1.5"><LuClock /> {clock(elapsed)}</span>
                  </div>
                  <ProgressBar value={null} label="Analyzing video" />
                  <p className="text-xs text-muted">Long videos can take several minutes. Keep this page open until the results appear.</p>
                </div>
              )}
            </>
          )}

          {error && <Alert className="mt-4" onRetry={file && phase === "idle" && !result ? analyze : undefined} onClose={() => setError("")}>{error}</Alert>}
        </section>

        <section className="card p-4 sm:p-5 lg:col-span-2 min-w-0" aria-label="Analysis results" aria-live="polite">
          <SectionTitle title="Results" description={result ? `${result.frames_processed} frames analyzed` : "Findings appear here after a run"} />

          {!result ? (
            busy ? (
              <div className="space-y-3">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-12" />)}</div>
            ) : (
              <EmptyState icon={LuFilm} title="No analysis yet">
                Every frame is checked. Repeated violations of the same type are logged once per cooldown window, so one worker isn't counted on every frame.
              </EmptyState>
            )
          ) : (
            <div className="space-y-5">
              {result.total_violations > 0 ? (
                <Alert tone="danger" title={`${result.total_violations} violation${result.total_violations > 1 ? "s" : ""} logged`}>
                  Each was saved to the violations log with the frame as evidence.
                </Alert>
              ) : (
                <Alert tone="ok" title="No violations found">No missing hard hat or vest was matched to a detected worker.</Alert>
              )}

              <dl className="grid grid-cols-2 gap-2.5">
                {[
                  ["Frames analyzed", result.frames_processed?.toLocaleString() ?? "—"],
                  ["Duration", result.duration_seconds != null ? clock(result.duration_seconds) : meta?.duration ? clock(meta.duration) : "—"],
                  ["Helmet missing", result.helmet_violations],
                  ["Vest missing", result.vest_violations],
                ].map(([label, v]) => (
                  <div key={label} className="rounded-lg border border-line bg-surface-2/50 px-3 py-2.5">
                    <dt className="text-xs text-muted">{label}</dt>
                    <dd className="text-xl font-semibold tabular-nums mt-0.5">{v}</dd>
                  </div>
                ))}
              </dl>

              {result.events?.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-muted mb-2">Timeline · select to jump to the frame</h3>
                  <ul className="divide-y divide-line border border-line rounded-lg max-h-64 overflow-y-auto">
                    {result.events.map((ev, i) => (
                      <li key={i}>
                        <button onClick={() => seek(ev.time)} className="w-full flex items-center gap-3 px-3 py-2 text-sm text-left hover:bg-surface-2">
                          <span className="tabular-nums font-mono text-xs text-muted w-12">{clock(ev.time)}</span>
                          {ev.type === "no_helmet" ? <LuTriangleAlert className="text-danger" /> : <LuTriangleAlert className="text-warning" />}
                          <span className="flex-1">{TYPE_LABEL[ev.type] ?? ev.type}</span>
                          <span className="tabular-nums text-muted">{Math.round(ev.confidence * 100)}%</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.total_violations > 0 ? (
                <Link to="/violations?source=video" className="btn btn-secondary w-full">Review in Violations <LuArrowRight /></Link>
              ) : (
                <p className="text-xs text-muted flex items-center gap-2"><LuCircleCheck className="text-primary" /> Nothing was added to the violations log.</p>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default VideoDetection;
