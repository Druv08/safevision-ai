import { useState, useRef, useEffect } from "react";
import API from "../services/api";
import { FaCamera, FaUpload, FaStop, FaPlay, FaExclamationTriangle, FaCheckCircle, FaFilm } from "react-icons/fa";

function VideoDetection() {
  const [video, setVideo] = useState(null);
  const [videoName, setVideoName] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [useWebcam, setUseWebcam] = useState(false);
  const [stream, setStream] = useState(null);

  const videoRef = useRef(null);
  const autoRecorderRef = useRef(null);

  useEffect(() => () => { if (stream) stream.getTracks().forEach((t) => t.stop()); }, [stream]);
  useEffect(() => { if (useWebcam && videoRef.current && stream) videoRef.current.srcObject = stream; }, [useWebcam, stream]);

  const startWebcam = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      setStream(mediaStream);
      setUseWebcam(true);
      setVideo(null);
      setVideoName("");
      setResult(null);

      const recordAndSend = () => {
        const recorder = new MediaRecorder(mediaStream, { mimeType: "video/webm" });
        const chunks = [];
        recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
        recorder.onstop = async () => {
          if (!chunks.length) return;
          const blob = new Blob(chunks, { type: "video/webm" });
          try {
            setLoading(true);
            const form = new FormData();
            form.append("video", new File([blob], "chunk.webm", { type: "video/webm" }));
            const res = await API.post("/detect-video", form);
            setResult(res.data);
          } catch (e) { console.error(e); }
          finally { setLoading(false); }
        };
        recorder.start();
        setTimeout(() => { if (recorder.state === "recording") recorder.stop(); }, 5000);
      };

      recordAndSend();
      autoRecorderRef.current = setInterval(recordAndSend, 5500);
    } catch (err) {
      alert("Webcam error: " + err.message);
    }
  };

  const stopWebcam = () => {
    clearInterval(autoRecorderRef.current);
    stream?.getTracks().forEach((t) => t.stop());
    setStream(null);
    setUseWebcam(false);
  };

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) { setVideo(f); setVideoName(f.name); setResult(null); }
  };

  const handleDetect = async () => {
    if (!video) return alert("Please select a video first.");
    try {
      setLoading(true);
      const form = new FormData();
      form.append("video", video);
      const r = await API.post("/detect-video", form, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(r.data);
    } catch (e) {
      console.error(e);
      alert(e.response ? JSON.stringify(e.response.data) : "Video detection failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">

      {/* Upload / Webcam Panel */}
      <div className="sv-panel rounded-2xl p-6">
        <div className="grid md:grid-cols-2 gap-6 mb-6">

          {/* File upload */}
          <div>
            <p className="sv-mono sv-fg-muted text-[9.5px] font-bold uppercase tracking-[0.16em] mb-3">
              Upload Video
            </p>
            <label className="sv-dropzone flex flex-col items-center justify-center w-full h-36 rounded-xl cursor-pointer group">
              <FaUpload className="sv-fg-dim text-2xl mb-2 transition-colors" />
              <span className="sv-fg-muted text-sm text-center px-4 truncate max-w-full">
                {videoName || "Click to choose a video"}
              </span>
              <span className="sv-mono sv-fg-faint text-[9px] uppercase tracking-[0.14em] mt-1.5">
                MP4 · AVI · MOV · WEBM
              </span>
              <input type="file" accept="video/*" onChange={handleFileChange} className="hidden" />
            </label>
          </div>

          {/* Webcam */}
          <div>
            <p className="sv-mono sv-fg-muted text-[9.5px] font-bold uppercase tracking-[0.16em] mb-3">
              Live CCTV / Webcam
            </p>
            <button
              onClick={useWebcam ? stopWebcam : startWebcam}
              className={`w-full h-36 rounded-xl flex flex-col items-center justify-center gap-2 font-semibold text-sm ${
                useWebcam
                  ? "tone-alert sv-dropzone-active"
                  : "sv-dropzone sv-fg-muted"
              }`}
            >
              {useWebcam
                ? <><FaStop className="text-xl" /> Stop Webcam</>
                : <><FaCamera className="text-xl" /> Open Webcam</>
              }
            </button>
          </div>
        </div>

        <button
          onClick={handleDetect}
          disabled={loading || !video}
          className="sv-gold-btn flex items-center gap-2 text-[var(--sv-on-accent)] px-6 py-2.5 rounded-xl font-bold text-sm disabled:opacity-35 disabled:cursor-not-allowed transition-shadow duration-300"
        >
          <FaPlay />
          {loading ? "Processing…" : "Detect PPE"}
        </button>
      </div>

      {/* Webcam Feed */}
      {useWebcam && (
        <div className="sv-panel rounded-2xl p-6">
          <div className="flex items-center gap-2.5 mb-4">
            <span
              className="sv-ink-alert w-2 h-2 rounded-full bg-current"
              style={{ animation: "sv-blink 1.4s ease-in-out infinite" }}
            />
            <h3 className="sv-fg font-bold">Live CCTV Video Feed</h3>
            {loading && (
              <span className="sv-mono sv-ink-gold text-[10px] uppercase tracking-[0.14em] ml-auto">
                Analyzing stream…
              </span>
            )}
          </div>
          <video ref={videoRef} autoPlay playsInline muted className="sv-bd w-full rounded-xl bg-black border" />
        </div>
      )}

      {/* Selected file info */}
      {videoName && !useWebcam && (
        <div className="sv-panel flex items-center gap-3 rounded-xl px-5 py-4">
          <FaFilm className="sv-ink-gold text-xl flex-shrink-0" />
          <div className="min-w-0">
            <p className="sv-mono sv-fg-muted text-[9px] font-bold uppercase tracking-[0.14em]">
              Selected Video
            </p>
            <p className="sv-fg text-sm font-medium truncate">{videoName}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="sv-panel rounded-2xl p-6 space-y-5">
          <h2 className="sv-fg text-lg font-bold">Video Analysis Results</h2>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {[
              { label: "Status",            val: result.status,            tone: "tone-ok"      },
              { label: "Total Violations",  val: result.total_violations,  tone: "tone-alert"   },
              { label: "Helmet Violations", val: result.helmet_violations, tone: "tone-gold"    },
              { label: "Vest Violations",   val: result.vest_violations,   tone: "tone-gold"    },
              { label: "Filename",          val: result.filename,          tone: "tone-neutral" },
            ].map((s) => (
              <div key={s.label} className={`${s.tone} sv-tone rounded-xl p-4`}>
                <p className="sv-mono sv-fg-muted text-[9px] font-bold uppercase tracking-[0.14em] mb-1.5">
                  {s.label}
                </p>
                <p className="sv-tone-ink text-lg font-extrabold truncate">{s.val}</p>
              </div>
            ))}
          </div>

          <div
            className={`${result.total_violations > 0 ? "tone-alert" : "tone-ok"} sv-tone-strong sv-tone-ink flex items-center gap-3 p-4 rounded-xl font-bold tracking-wide`}
          >
            {result.total_violations > 0 ? <FaExclamationTriangle className="text-xl" /> : <FaCheckCircle className="text-xl" />}
            {result.total_violations > 0 ? `${result.total_violations} VIOLATION(S) DETECTED` : "NO VIOLATIONS FOUND"}
          </div>
        </div>
      )}
    </div>
  );
}

export default VideoDetection;
