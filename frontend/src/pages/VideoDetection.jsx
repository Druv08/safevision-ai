import { useState, useRef, useEffect } from "react";
import API from "../services/api";

function VideoDetection() {
  const [video, setVideo] = useState(null);
  const [videoName, setVideoName] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const [useWebcam, setUseWebcam] = useState(false);
  const [stream, setStream] = useState(null);
  const autoRecorderRef = useRef(null);
  const videoRef = useRef(null);

  useEffect(() => {
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [stream]);

  useEffect(() => {
    if (useWebcam && videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [useWebcam, stream]);

  const startWebcam = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      setStream(mediaStream);
      setUseWebcam(true);
      setVideo(null);
      setVideoName("");
      setResult(null);

      const recordAndSend = () => {
        const mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'video/webm' });
        const chunks = [];
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };
        mediaRecorder.onstop = async () => {
          if (chunks.length === 0) return;
          const blob = new Blob(chunks, { type: 'video/webm' });
          const file = new File([blob], "cctv-chunk.webm", { type: "video/webm" });
          try {
            setLoading(true);
            const formData = new FormData();
            formData.append("video", file);
            const res = await API.post("/detect-video", formData);
            setResult(res.data);
          } catch(e) {
            console.error(e);
          } finally {
            setLoading(false);
          }
        };
        mediaRecorder.start();
        setTimeout(() => {
          if (mediaRecorder.state === "recording") mediaRecorder.stop();
        }, 5000);
      };

      recordAndSend();
      const loop = setInterval(recordAndSend, 5500);
      autoRecorderRef.current = loop;

    } catch (err) {
      alert("Error accessing webcam: " + err.message);
    }
  };

  const stopWebcam = () => {
    if (autoRecorderRef.current) clearInterval(autoRecorderRef.current);
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    setUseWebcam(false);
  };

  const handleVideoChange = (e) => {
    const selected = e.target.files[0];

    if (selected) {
      setVideo(selected);
      setVideoName(selected.name);
      setResult(null);
    }
  };

  const handleDetect = async () => {
    if (!video) {
      alert("Please select a video first.");
      return;
    }

    try {
      setLoading(true);

      const formData = new FormData();
      formData.append("video", video);

      const response = await API.post(
        "/detect-video",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      setResult(response.data);
    } catch (error) {
      console.error(error);

      if (error.response) {
        alert(JSON.stringify(error.response.data));
      } else {
        alert("Video detection failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">
        Video Detection
      </h1>

      <div className="bg-white dark:bg-slate-800 p-6 rounded-xl shadow">
        <div className="flex flex-col xl:flex-row gap-4 mb-6">
          <div className="flex-1 flex flex-col gap-3">
             <label className="font-semibold dark:text-white">Upload File</label>
             <input
               type="file"
               accept="video/*"
               onChange={handleVideoChange}
               className="
                 block w-full text-sm
                 text-gray-900 dark:text-white
                 file:mr-4 file:py-2 file:px-4
                 file:rounded-lg file:border-0
                 file:text-sm file:font-semibold
                 file:bg-blue-600 file:text-white
                 hover:file:bg-blue-700
                 cursor-pointer
               "
             />
          </div>

          <div className="flex items-center justify-center">
            <span className="font-bold text-gray-400 dark:text-gray-500">OR</span>
          </div>

          <div className="flex-1 flex flex-col gap-3">
             <label className="font-semibold dark:text-white">Use CCTV / Webcam</label>
             <button
               onClick={useWebcam ? stopWebcam : startWebcam}
               className="bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900 dark:bg-slate-700 dark:hover:bg-slate-600 transition w-full sm:w-auto self-start"
             >
               {useWebcam ? "Close Webcam" : "Open Webcam"}
             </button>
          </div>
          
          <div className="flex-none flex items-end">
            <button
              onClick={handleDetect}
              disabled={loading || !video}
              className="bg-blue-600 text-white px-8 py-2 rounded-lg hover:bg-blue-700 w-full xl:w-auto h-10 disabled:opacity-50"
            >
              {loading ? "Processing..." : "Detect PPE"}
            </button>
          </div>
        </div>

        {useWebcam && (
          <div className="mb-6 bg-gray-100 dark:bg-slate-700 p-4 rounded-xl flex flex-col items-center shadow-inner">
            <h3 className="font-semibold text-lg mb-3 dark:text-white flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
              Live CCTV Video Processing
            </h3>
            <video ref={videoRef} autoPlay playsInline muted className="w-full max-w-2xl rounded-lg shadow-md bg-black border-2 border-gray-300 dark:border-slate-600" />
            <p className="text-gray-500 dark:text-gray-300 font-semibold mt-4 animate-pulse">Analyzing video stream in real-time...</p>
          </div>
        )}

        {videoName && (
          <div className="mt-4">
            <strong>Selected Video:</strong> {videoName}
          </div>
        )}

        {result && (
          <div className="mt-6 p-5 bg-gray-100 dark:bg-slate-700 rounded-lg border border-gray-200 dark:border-slate-600">
            <h2 className="text-xl font-bold mb-4 text-gray-800 dark:text-white">
              Video Analysis Results
            </h2>

            <div className="space-y-3 text-gray-700 dark:text-gray-200">
              <p>
                <strong>Filename:</strong>{" "}
                {result.filename}
              </p>

              <p>
                <strong>Status:</strong>{" "}
                <span className="text-green-600 dark:text-green-400 font-semibold">
                  {result.status}
                </span>
              </p>

              <p>
                <strong>Total Violations:</strong>{" "}
                {result.total_violations}
              </p>

              <p>
                <strong>Helmet Violations:</strong>{" "}
                {result.helmet_violations}
              </p>

              <p>
                <strong>Vest Violations:</strong>{" "}
                {result.vest_violations}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default VideoDetection;