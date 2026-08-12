import { useState, useRef, useEffect } from "react";
import API from "../services/api";
import { FaCamera, FaUpload, FaStop, FaSearch, FaCheckCircle, FaExclamationTriangle } from "react-icons/fa";

const CLASS_NAMES = { 0: "Person", 1: "Helmet", 2: "No Helmet", 3: "Vest", 4: "No Vest" };

function ImageDetection() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [useWebcam, setUseWebcam] = useState(false);
  const [stream, setStream] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const autoDetectRef = useRef(null);

  useEffect(() => () => { if (stream) stream.getTracks().forEach((t) => t.stop()); }, [stream]);
  useEffect(() => { if (useWebcam && videoRef.current && stream) videoRef.current.srcObject = stream; }, [useWebcam, stream]);

  const startWebcam = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
      setStream(mediaStream);
      setUseWebcam(true);
      setFile(null);
      setPreview(null);
      const detectFrame = () => {
        if (!videoRef.current || !canvasRef.current) return;
        const video = videoRef.current;
        if (video.videoWidth === 0) return;
        const canvas = canvasRef.current;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);
        canvas.toBlob(async (blob) => {
          const formData = new FormData();
          formData.append("image", new File([blob], "frame.jpg", { type: "image/jpeg" }));
          try { setLoading(true); const r = await API.post("/detect-image", formData); setResult(r.data); }
          catch (e) { console.error(e); }
          finally { setLoading(false); }
        }, "image/jpeg");
      };
      autoDetectRef.current = setInterval(detectFrame, 3000);
    } catch (err) {
      alert("Webcam error: " + err.message);
    }
  };

  const stopWebcam = () => {
    clearInterval(autoDetectRef.current);
    stream?.getTracks().forEach((t) => t.stop());
    setStream(null);
    setUseWebcam(false);
  };

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) { setFile(f); setPreview(URL.createObjectURL(f)); setResult(null); }
  };

  const handleDetect = async () => {
    if (!file) return alert("Please select an image first.");
    try {
      setLoading(true);
      const form = new FormData();
      form.append("image", file);
      const r = await API.post("/detect-image", form, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(r.data);
    } catch (e) {
      console.error(e);
      alert(e.response ? JSON.stringify(e.response.data) : "Detection failed.");
    } finally {
      setLoading(false);
    }
  };

  const hasViolation = result?.detections?.some((d) => d.class_id === 2 || d.class_id === 4) ?? false;

  return (
    <div className="space-y-6 max-w-5xl">

      {/* Upload / Webcam Panel */}
      <div className="sv-panel rounded-2xl p-6">
        <div className="grid md:grid-cols-2 gap-6 mb-6">

          {/* File upload */}
          <div>
            <p className="sv-mono sv-fg-muted text-[9.5px] font-bold uppercase tracking-[0.16em] mb-3">
              Upload Image
            </p>
            <label className="sv-dropzone flex flex-col items-center justify-center w-full h-36 rounded-xl cursor-pointer group">
              <FaUpload className="sv-fg-dim text-2xl mb-2 transition-colors" />
              <span className="sv-fg-muted text-sm px-4 text-center truncate max-w-full">
                {file ? file.name : "Click to choose an image"}
              </span>
              <span className="sv-mono sv-fg-faint text-[9px] uppercase tracking-[0.14em] mt-1.5">
                PNG · JPG · JPEG
              </span>
              <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
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

        {/* Detect button */}
        <button
          onClick={handleDetect}
          disabled={loading || !file}
          className="sv-gold-btn flex items-center gap-2 text-[var(--sv-on-accent)] px-6 py-2.5 rounded-xl font-bold text-sm disabled:opacity-35 disabled:cursor-not-allowed transition-shadow duration-300"
        >
          <FaSearch />
          {loading ? "Detecting…" : "Detect PPE"}
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
            <h3 className="sv-fg font-bold">Live CCTV Feed</h3>
            {loading && (
              <span className="sv-mono sv-ink-gold text-[10px] uppercase tracking-[0.14em] ml-auto">
                Analyzing…
              </span>
            )}
          </div>
          <video ref={videoRef} autoPlay playsInline className="sv-bd w-full rounded-xl bg-black border" />
          <canvas ref={canvasRef} className="hidden" />
        </div>
      )}

      {/* Image Preview */}
      {preview && (
        <div className="sv-panel rounded-2xl p-6">
          <p className="sv-mono sv-fg-muted text-[9.5px] font-bold uppercase tracking-[0.16em] mb-4">
            Preview
          </p>
          <img src={preview} alt="Preview" className="sv-bd max-w-md rounded-xl border" />
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="sv-panel rounded-2xl p-6 space-y-6">
          <h2 className="sv-fg text-lg font-bold">Detection Results</h2>

          {/* Summary cards */}
          {result.summary && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[
                { label: "Total Persons", val: result.summary.total_persons, tone: "tone-neutral" },
                { label: "Helmet Worn",   val: result.summary.helmet_worn,   tone: "tone-ok"      },
                { label: "No Helmet",     val: result.summary.no_helmet,     tone: "tone-alert"   },
                { label: "Vest Worn",     val: result.summary.vest_worn,     tone: "tone-ok"      },
                { label: "No Vest",       val: result.summary.no_vest,       tone: "tone-alert"   },
              ].map((s) => (
                <div key={s.label} className={`${s.tone} sv-tone rounded-xl p-3 text-center`}>
                  <div className="sv-tone-ink text-2xl font-extrabold">{s.val}</div>
                  <div className="sv-mono sv-fg-muted text-[8.5px] font-bold uppercase tracking-[0.12em] mt-1.5">
                    {s.label}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Raw detections */}
          {result.detections.length > 0 && (
            <div>
              <p className="sv-mono sv-fg-muted text-[9.5px] font-bold uppercase tracking-[0.16em] mb-3">
                Raw Detections
              </p>
              <div className="flex flex-wrap gap-2">
                {result.detections.map((d, i) => {
                  const bad = d.class_id === 2 || d.class_id === 4;
                  return (
                    <span
                      key={i}
                      className={`${bad ? "tone-alert" : "tone-ok"} sv-tone sv-tone-ink sv-mono px-3 py-1.5 rounded-lg text-[11px] font-bold`}
                    >
                      {CLASS_NAMES[d.class_id]} — {(d.confidence * 100).toFixed(1)}%
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* Verdict */}
          <div
            className={`${hasViolation ? "tone-alert" : "tone-ok"} sv-tone-strong sv-tone-ink flex items-center gap-3 p-4 rounded-xl font-bold tracking-wide`}
          >
            {hasViolation ? <FaExclamationTriangle className="text-xl" /> : <FaCheckCircle className="text-xl" />}
            {hasViolation ? "VIOLATION DETECTED" : "ALL SAFE"}
          </div>
        </div>
      )}
    </div>
  );
}

export default ImageDetection;
