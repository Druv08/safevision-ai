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
      <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl p-6">
        <div className="grid md:grid-cols-2 gap-6 mb-6">

          {/* File upload */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Upload Image</p>
            <label className="flex flex-col items-center justify-center w-full h-36 border-2 border-dashed border-white/10 rounded-xl cursor-pointer hover:border-blue-500/40 hover:bg-blue-500/[0.03] transition-all group">
              <FaUpload className="text-2xl text-slate-500 group-hover:text-blue-400 mb-2 transition-colors" />
              <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                {file ? file.name : "Click to choose an image"}
              </span>
              <span className="text-xs text-slate-600 mt-1">PNG, JPG, JPEG</span>
              <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
            </label>
          </div>

          {/* Webcam */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Live CCTV / Webcam</p>
            <button
              onClick={useWebcam ? stopWebcam : startWebcam}
              className={`w-full h-36 rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 transition-all font-medium text-sm ${
                useWebcam
                  ? "border-red-500/40 bg-red-500/[0.05] text-red-400 hover:bg-red-500/10"
                  : "border-white/10 text-slate-400 hover:border-emerald-500/40 hover:bg-emerald-500/[0.03] hover:text-emerald-400"
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
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-[0_0_20px_rgba(37,99,235,0.3)]"
        >
          <FaSearch />
          {loading ? "Detecting…" : "Detect PPE"}
        </button>
      </div>

      {/* Webcam Feed */}
      {useWebcam && (
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <h3 className="font-semibold text-white">Live CCTV Feed</h3>
            {loading && <span className="text-xs text-blue-400 ml-auto animate-pulse">Analyzing…</span>}
          </div>
          <video ref={videoRef} autoPlay playsInline className="w-full rounded-xl bg-black border border-white/[0.06]" />
          <canvas ref={canvasRef} className="hidden" />
        </div>
      )}

      {/* Image Preview */}
      {preview && (
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-6">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Preview</p>
          <img src={preview} alt="Preview" className="max-w-md rounded-xl border border-white/[0.08]" />
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-6 space-y-6">
          <h2 className="text-lg font-bold text-white">Detection Results</h2>

          {/* Summary cards */}
          {result.summary && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[
                { label: "Total Persons", val: result.summary.total_persons, c: "text-blue-400",    b: "border-blue-500/20",    bg: "bg-blue-500/10"    },
                { label: "Helmet Worn",   val: result.summary.helmet_worn,   c: "text-emerald-400", b: "border-emerald-500/20", bg: "bg-emerald-500/10" },
                { label: "No Helmet",     val: result.summary.no_helmet,     c: "text-red-400",     b: "border-red-500/20",     bg: "bg-red-500/10"     },
                { label: "Vest Worn",     val: result.summary.vest_worn,     c: "text-emerald-400", b: "border-emerald-500/20", bg: "bg-emerald-500/10" },
                { label: "No Vest",       val: result.summary.no_vest,       c: "text-red-400",     b: "border-red-500/20",     bg: "bg-red-500/10"     },
              ].map((s) => (
                <div key={s.label} className={`${s.bg} border ${s.b} rounded-xl p-3 text-center`}>
                  <div className={`text-2xl font-black ${s.c}`}>{s.val}</div>
                  <div className="text-[11px] text-slate-400 mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Raw detections */}
          {result.detections.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Raw Detections</p>
              <div className="flex flex-wrap gap-2">
                {result.detections.map((d, i) => (
                  <span key={i} className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${
                    d.class_id === 2 || d.class_id === 4
                      ? "bg-red-500/10 border-red-500/20 text-red-300"
                      : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                  }`}>
                    {CLASS_NAMES[d.class_id]} — {(d.confidence * 100).toFixed(1)}%
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Verdict */}
          <div className={`flex items-center gap-3 p-4 rounded-xl border font-bold ${
            hasViolation
              ? "bg-red-500/10 border-red-500/30 text-red-300"
              : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
          }`}>
            {hasViolation ? <FaExclamationTriangle className="text-xl" /> : <FaCheckCircle className="text-xl" />}
            {hasViolation ? "VIOLATION DETECTED" : "ALL SAFE"}
          </div>
        </div>
      )}
    </div>
  );
}

export default ImageDetection;
