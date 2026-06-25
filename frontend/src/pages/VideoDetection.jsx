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
      <div className="bg-white/[0.03] backdrop-blur-sm border border-white/[0.08] rounded-2xl p-6">
        <div className="grid md:grid-cols-2 gap-6 mb-6">

          {/* File upload */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Upload Video</p>
            <label className="flex flex-col items-center justify-center w-full h-36 border-2 border-dashed border-white/10 rounded-xl cursor-pointer hover:border-blue-500/40 hover:bg-blue-500/[0.03] transition-all group">
              <FaUpload className="text-2xl text-slate-500 group-hover:text-blue-400 mb-2 transition-colors" />
              <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors text-center px-4 truncate max-w-full">
                {videoName || "Click to choose a video"}
              </span>
              <span className="text-xs text-slate-600 mt-1">MP4, AVI, MOV, WEBM</span>
              <input type="file" accept="video/*" onChange={handleFileChange} className="hidden" />
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

        <button
          onClick={handleDetect}
          disabled={loading || !video}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-[0_0_20px_rgba(37,99,235,0.3)]"
        >
          <FaPlay />
          {loading ? "Processing…" : "Detect PPE"}
        </button>
      </div>

      {/* Webcam Feed */}
      {useWebcam && (
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <h3 className="font-semibold text-white">Live CCTV Video Feed</h3>
            {loading && <span className="text-xs text-blue-400 ml-auto animate-pulse">Analyzing stream…</span>}
          </div>
          <video ref={videoRef} autoPlay playsInline muted className="w-full rounded-xl bg-black border border-white/[0.06]" />
        </div>
      )}

      {/* Selected file info */}
      {videoName && !useWebcam && (
        <div className="flex items-center gap-3 bg-white/[0.03] border border-white/[0.08] rounded-xl px-5 py-4">
          <FaFilm className="text-blue-400 text-xl flex-shrink-0" />
          <div>
            <p className="text-xs text-slate-500 font-medium">Selected Video</p>
            <p className="text-sm text-white font-medium">{videoName}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-6 space-y-5">
          <h2 className="text-lg font-bold text-white">Video Analysis Results</h2>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {[
              { label: "Status",            val: result.status,            c: "text-emerald-400", b: "border-emerald-500/20", bg: "bg-emerald-500/10" },
              { label: "Total Violations",  val: result.total_violations,  c: "text-red-400",     b: "border-red-500/20",     bg: "bg-red-500/10"     },
              { label: "Helmet Violations", val: result.helmet_violations, c: "text-orange-400",  b: "border-orange-500/20",  bg: "bg-orange-500/10"  },
              { label: "Vest Violations",   val: result.vest_violations,   c: "text-yellow-400",  b: "border-yellow-500/20",  bg: "bg-yellow-500/10"  },
              { label: "Filename",          val: result.filename,          c: "text-slate-300",   b: "border-white/[0.08]",   bg: "bg-white/[0.03]"   },
            ].map((s) => (
              <div key={s.label} className={`${s.bg} border ${s.b} rounded-xl p-4`}>
                <p className="text-[11px] text-slate-400 font-medium uppercase tracking-wider mb-1">{s.label}</p>
                <p className={`text-lg font-bold ${s.c} truncate`}>{s.val}</p>
              </div>
            ))}
          </div>

          <div className={`flex items-center gap-3 p-4 rounded-xl border font-bold ${
            result.total_violations > 0
              ? "bg-red-500/10 border-red-500/30 text-red-300"
              : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
          }`}>
            {result.total_violations > 0 ? <FaExclamationTriangle className="text-xl" /> : <FaCheckCircle className="text-xl" />}
            {result.total_violations > 0 ? `${result.total_violations} VIOLATION(S) DETECTED` : "NO VIOLATIONS FOUND"}
          </div>
        </div>
      )}
    </div>
  );
}

export default VideoDetection;
