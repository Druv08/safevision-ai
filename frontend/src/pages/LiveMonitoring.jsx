import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  LuCamera, LuCameraOff, LuMaximize, LuRefreshCw, LuSquare, LuPlay, LuArrowRight, LuNetwork, LuTriangleAlert, LuCircleCheck,
} from "react-icons/lu";
import API, { apiError } from "../services/api";
import { openCamera } from "../services/camera";
import { verdictFor } from "../services/detection";
import { PageHeader, SectionTitle, Segmented, Alert, EmptyState, Spinner } from "../components/ui";
import DetectionOverlay from "../components/DetectionOverlay";
import { SummaryGrid } from "./ImageDetection";

const FRAME_MS = 3000;
const CLIP_MS = 5000;
const MAX_EVENTS = 25;
// Formats the backend accepts, in order of preference (Safari has no webm recorder).
const RECORDER_TYPES = [["video/webm", "webm"], ["video/mp4", "mp4"]];
const MODES = [
  { value: "frames", label: `Frame every ${FRAME_MS / 1000}s` },
  { value: "clips", label: `${CLIP_MS / 1000}s clips` },
];
const STATUS = {
  idle:       { tone: "tone-neutral", label: "Offline" },
  connecting: { tone: "tone-info",    label: "Connecting" },
  live:       { tone: "tone-ok",      label: "Demo running" },
  error:      { tone: "tone-danger",  label: "Disconnected" },
};
const cameraSupported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

function LiveMonitoring() {
  const [devices, setDevices] = useState([]);
  const [deviceId, setDeviceId] = useState("");
  const [mode, setMode] = useState("frames");
  const [status, setStatus] = useState("idle");
  const [cameraError, setCameraError] = useState("");
  const [requestError, setRequestError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [last, setLast] = useState(null); // { kind, data, at, ms, w, h }
  const [stats, setStats] = useState({ analyzed: 0, violations: 0, failed: 0, since: null });
  const [events, setEvents] = useState([]);
  const [showBoxes, setShowBoxes] = useState(true);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const stageRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const inFlightRef = useRef(false);

  const listDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const all = await navigator.mediaDevices.enumerateDevices();
    setDevices(all.filter((d) => d.kind === "videoinput"));
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- listDevices() only sets state after its await
  useEffect(() => { listDevices(); }, [listDevices]);

  const teardown = () => {
    clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    inFlightRef.current = false;
  };
  useEffect(() => teardown, []); // release the camera when leaving the page

  const record = (ok, data, kind, startedAt, dims) => {
    const at = new Date();
    if (!ok) {
      setStats((s) => ({ ...s, failed: s.failed + 1 }));
      return;
    }
    const n = kind === "frame" ? data.summary.no_helmet + data.summary.no_vest : data.total_violations;
    setLast({ kind, data, at, ms: Date.now() - startedAt, ...dims });
    setStats((s) => ({ ...s, analyzed: s.analyzed + 1, violations: s.violations + n }));
    if (n > 0) {
      const helmet = kind === "frame" ? data.summary.no_helmet : data.helmet_violations;
      const vest = kind === "frame" ? data.summary.no_vest : data.vest_violations;
      setEvents((e) => [{ at, helmet, vest }, ...e].slice(0, MAX_EVENTS));
    }
    setRequestError("");
  };

  const sendFrame = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0 || inFlightRef.current) return; // skip while busy
    const dims = { w: video.videoWidth, h: video.videoHeight };
    canvas.width = dims.w;
    canvas.height = dims.h;
    canvas.getContext("2d").drawImage(video, 0, 0);
    inFlightRef.current = true;
    setAnalyzing(true);
    const startedAt = Date.now();
    canvas.toBlob(async (blob) => {
      try {
        if (!blob) throw new Error("Could not capture a frame.");
        const form = new FormData();
        form.append("image", new File([blob], "frame.jpg", { type: "image/jpeg" }));
        form.append("source", "camera");
        const r = await API.post("/detect-image", form);
        if (streamRef.current) record(true, r.data, "frame", startedAt, dims);
      } catch (e) {
        record(false);
        setRequestError(apiError(e, "Frame analysis failed."));
      } finally {
        inFlightRef.current = false;
        setAnalyzing(false);
      }
    }, "image/jpeg", 0.85);
  };

  const recordClip = (stream, mimeType, ext) => {
    if (!stream.active) return;
    const recorder = new MediaRecorder(stream, { mimeType });
    const chunks = [];
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
    recorder.onstop = async () => {
      // Drop the clip if the camera stopped or the previous clip is still being analysed.
      if (!chunks.length || !stream.active || inFlightRef.current) return;
      inFlightRef.current = true;
      setAnalyzing(true);
      const startedAt = Date.now();
      try {
        const form = new FormData();
        form.append("video", new File(chunks, `clip.${ext}`, { type: mimeType }));
        form.append("source", "camera");
        const r = await API.post("/detect-video", form);
        if (streamRef.current) record(true, r.data, "clip", startedAt);
      } catch (e) {
        record(false);
        setRequestError(apiError(e, "Clip analysis failed."));
      } finally {
        inFlightRef.current = false;
        setAnalyzing(false);
      }
    };
    recorder.start();
    setTimeout(() => { if (recorder.state === "recording") recorder.stop(); }, CLIP_MS);
  };

  const start = async () => {
    setCameraError("");
    setRequestError("");
    let recorderType = null;
    if (mode === "clips") {
      recorderType = typeof MediaRecorder !== "undefined" && RECORDER_TYPES.find(([t]) => MediaRecorder.isTypeSupported(t));
      if (!recorderType) {
        setCameraError("This browser cannot record video clips. Use frame mode instead.");
        return;
      }
    }
    setStatus("connecting");
    try {
      const stream = await openCamera({ video: deviceId ? { deviceId: { exact: deviceId } } : true, audio: false });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      stream.getVideoTracks()[0].onended = () => {
        teardown();
        setStatus("error");
        setCameraError("The camera stopped sending video (unplugged or taken by another app).");
      };
      setStatus("live");
      setLast(null);
      setStats({ analyzed: 0, violations: 0, failed: 0, since: new Date() });
      setEvents([]);
      listDevices(); // labels become readable once permission is granted
      if (mode === "frames") {
        timerRef.current = setInterval(sendFrame, FRAME_MS);
      } else {
        const [mimeType, ext] = recorderType;
        recordClip(stream, mimeType, ext);
        timerRef.current = setInterval(() => recordClip(stream, mimeType, ext), CLIP_MS + 500);
      }
    } catch (e) {
      teardown();
      setStatus("error");
      setCameraError(e.message);
    }
  };

  const stop = () => {
    teardown();
    setStatus("idle");
    setAnalyzing(false);
  };

  const fullscreen = () => stageRef.current?.requestFullscreen?.();

  const live = status === "live";
  // "Disconnected" only if a session actually ran; otherwise the camera never opened.
  const s = status === "error" && !stats.since ? { tone: "tone-danger", label: "Unavailable" } : STATUS[status];
  const activeLabel = devices.find((d) => d.deviceId === deviceId)?.label || (devices.length ? devices[0].label : "") || "Browser camera";
  const verdict = last?.kind === "frame" ? verdictFor(last.data.summary) : null;

  return (
    <div>
      <PageHeader
        title="Webcam demo"
        description="Demo mode: sends frames or short clips from a camera attached to this browser for analysis. It is not continuous site monitoring; for that, add network cameras on the Cameras page."
        actions={
          live ? (
            <button className="btn btn-danger" onClick={stop}><LuSquare /> Stop demo</button>
          ) : (
            <button className="btn btn-primary" onClick={start} disabled={!cameraSupported || status === "connecting"}>
              {status === "connecting" ? <Spinner /> : <LuPlay />} {status === "error" ? "Reconnect" : "Start demo"}
            </button>
          )
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Feed */}
        <section className="card overflow-hidden xl:col-span-2 min-w-0" aria-label="Camera feed">
          <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-line">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <LuCamera className="text-muted flex-shrink-0" aria-hidden="true" />
              <span className="text-sm font-medium truncate">{activeLabel}</span>
              <span className={`badge ${s.tone}`} role="status"><span className={`dot ${live ? "animate-live" : ""}`} />{s.label}</span>
            </div>
            <Segmented size="sm" label="Analysis mode" value={mode} onChange={setMode} options={MODES} />
            <button className="btn btn-ghost btn-sm btn-icon" onClick={fullscreen} disabled={!live || !document.fullscreenEnabled} aria-label="Full screen" data-tip="Full screen" data-tip-align="end">
              <LuMaximize />
            </button>
          </div>

          <div ref={stageRef} className="relative bg-black aspect-video flex items-center justify-center">
            <div className={`relative max-w-full max-h-full ${live ? "" : "hidden"}`}>
              <video ref={videoRef} autoPlay playsInline muted className="block max-w-full max-h-full" />
              {live && showBoxes && last?.kind === "frame" && (
                <DetectionOverlay detections={last.data.detections} width={last.w} height={last.h} />
              )}
            </div>
            <canvas ref={canvasRef} className="hidden" />

            {!live && (
              <div className="absolute inset-0 flex items-center justify-center p-6">
                {status === "connecting" ? (
                  <p className="text-sm text-white/80 flex items-center gap-2"><Spinner /> Waiting for camera permission…</p>
                ) : !cameraSupported ? (
                  <EmptyState icon={LuCameraOff} title="Camera access unavailable" className="text-white">
                    Camera access needs HTTPS or localhost, and a browser that supports it.
                  </EmptyState>
                ) : (
                  <EmptyState
                    icon={status === "error" ? LuCameraOff : LuCamera}
                    title={status === "error" ? (stats.since ? "Camera disconnected" : "Couldn't start the camera") : "Camera is off"}
                    action={
                      <button className="btn btn-primary" onClick={start}>
                        <LuPlay /> {status === "error" ? "Reconnect" : "Start demo"}
                      </button>
                    }
                  >
                    {status === "error" ? cameraError : "Your browser will ask for permission to use the camera."}
                  </EmptyState>
                )}
              </div>
            )}

            {live && (
              <div className="absolute left-3 bottom-3 right-3 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
                <span className="badge bg-black/70 border-white/10 text-white/90 h-7">
                  {analyzing ? <><Spinner /> Analyzing {mode === "frames" ? "frame" : "clip"}…</>
                    : last ? `Last result ${last.at.toLocaleTimeString()} · ${(last.ms / 1000).toFixed(1)}s`
                    : mode === "frames" ? "First frame in a few seconds…" : "Recording first clip…"}
                </span>
                {mode === "frames" && last && (
                  <label className="badge bg-black/70 border-white/10 text-white/90 h-7 pointer-events-auto cursor-pointer">
                    <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} className="accent-[var(--primary)]" />
                    Boxes
                  </label>
                )}
              </div>
            )}
          </div>

          <div className="p-4 space-y-3">
            {cameraError && status !== "error" && <Alert onClose={() => setCameraError("")}>{cameraError}</Alert>}
            {requestError && live && (
              <Alert tone="warning" onClose={() => setRequestError("")} title="Analysis request failed. The camera keeps running.">
                {requestError}
              </Alert>
            )}
            <p className="text-xs text-muted">
              {mode === "frames"
                ? `A still frame is sent every ${FRAME_MS / 1000}s. If the previous frame is still being analyzed, the next one is skipped.`
                : `The camera is recorded in ${CLIP_MS / 1000}s clips and each clip is analyzed frame by frame.`}
              {live && " Stop the demo to change the mode or camera."}
            </p>
          </div>
        </section>

        {/* Side panel */}
        <div className="space-y-4 min-w-0">
          <section className="card p-4 sm:p-5" aria-label="Camera sources">
            <SectionTitle
              title="Camera sources"
              description={`${devices.length} camera${devices.length === 1 ? "" : "s"} on this device`}
              action={<button className="btn btn-ghost btn-sm btn-icon" onClick={listDevices} aria-label="Refresh camera list" data-tip="Refresh" data-tip-align="end"><LuRefreshCw /></button>}
            />
            <fieldset disabled={live || status === "connecting"} className="space-y-1.5">
              <legend className="sr-only">Choose a camera</legend>
              {devices.length === 0 && <p className="text-sm text-muted">No camera found yet. Start the demo to grant access.</p>}
              {devices.map((d, i) => {
                const id = d.deviceId || `cam-${i}`;
                const checked = (deviceId || devices[0].deviceId) === d.deviceId;
                return (
                  <label key={id} className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-sm cursor-pointer ${checked ? "border-primary/50 bg-primary/5" : "border-line hover:bg-surface-2"}`}>
                    <input type="radio" name="camera" value={d.deviceId} checked={checked} onChange={() => setDeviceId(d.deviceId)} className="accent-[var(--primary)]" />
                    <span className="truncate">{d.label || `Camera ${i + 1}`}</span>
                  </label>
                );
              })}
              <Link to="/cameras" className="flex items-start gap-3 rounded-lg border border-dashed border-line px-3 py-2.5 text-sm hover:bg-surface-2">
                <LuNetwork className="mt-0.5 text-muted flex-shrink-0" aria-hidden="true" />
                <div>
                  <p className="font-medium">Network cameras (RTSP)</p>
                  <p className="text-xs text-muted mt-0.5">Analysed continuously on the server, with zones. Set them up on the Cameras page.</p>
                </div>
              </Link>
            </fieldset>
          </section>

          <section className="card p-4 sm:p-5" aria-label="Session" aria-live="polite">
            <SectionTitle
              title="This session"
              description={stats.since ? `Since ${stats.since.toLocaleTimeString()}` : "Starts when monitoring begins"}
            />
            <dl className="grid grid-cols-3 gap-2.5">
              {[
                [mode === "frames" ? "Frames" : "Clips", stats.analyzed],
                ["Violations", stats.violations],
                ["Failed", stats.failed],
              ].map(([label, n]) => (
                <div key={label} className="rounded-lg border border-line bg-surface-2/50 px-3 py-2">
                  <dt className="text-xs text-muted">{label}</dt>
                  <dd className="text-lg font-semibold tabular-nums">{n}</dd>
                </div>
              ))}
            </dl>

            {verdict && (
              <div className="mt-4 space-y-3">
                <Alert tone={verdict.tone} title={`Latest frame: ${verdict.title}`} />
                <SummaryGrid summary={last.data.summary} />
              </div>
            )}
            {last?.kind === "clip" && (
              <div className="mt-4">
                {last.data.total_violations > 0
                  ? <Alert tone="danger" title={`Latest clip: ${last.data.total_violations} violation(s) logged`} />
                  : <Alert tone="ok" title="Latest clip: no violations" />}
              </div>
            )}
          </section>

          <section className="card p-4 sm:p-5" aria-label="Recent detections">
            <SectionTitle
              title="Recent detections"
              description="Violations flagged in this session"
              action={<Link to="/violations?source=camera" className="btn btn-ghost btn-sm">All <LuArrowRight /></Link>}
            />
            {events.length === 0 ? (
              <p className="text-sm text-muted flex items-center gap-2"><LuCircleCheck className="text-primary" /> No violations flagged yet.</p>
            ) : (
              <ul className="divide-y divide-line -my-2">
                {events.map((e, i) => (
                  <li key={i} className="flex items-center gap-3 py-2 text-sm">
                    <LuTriangleAlert className="text-danger flex-shrink-0" aria-hidden="true" />
                    <span className="flex-1 min-w-0 truncate">
                      {[e.helmet && `${e.helmet}× helmet missing`, e.vest && `${e.vest}× vest missing`].filter(Boolean).join(", ")}
                    </span>
                    <span className="tabular-nums text-xs text-muted">{e.at.toLocaleTimeString()}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export default LiveMonitoring;
