import { useState, useRef, useEffect } from "react";
import API from "../services/api";

function ImageDetection() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const classNames = {
    0: "Person",
    1: "Helmet",
    2: "No Helmet",
    3: "Vest",
    4: "No Vest",
  };

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const autoDetectRef = useRef(null);
  const [useWebcam, setUseWebcam] = useState(false);
  const [stream, setStream] = useState(null);

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
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
      setStream(mediaStream);
      setUseWebcam(true);
      setFile(null);
      setPreview(null);
      
      const detectFrame = () => {
        if (!videoRef.current || !canvasRef.current) return;
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (video.videoWidth === 0) return; 

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        canvas.toBlob(async (blob) => {
          const capturedFile = new File([blob], "cctv-frame.jpg", { type: "image/jpeg" });
          const formData = new FormData();
          formData.append("image", capturedFile);
          try {
            setLoading(true);
            const response = await API.post("/detect-image", formData);
            setResult(response.data);
          } catch (error) {
            console.error(error);
          } finally {
            setLoading(false);
          }
        }, "image/jpeg");
      };

      const loop = setInterval(detectFrame, 3000);
      autoDetectRef.current = loop;

    } catch (err) {
      alert("Error accessing webcam: " + err.message);
    }
  };

  const stopWebcam = () => {
    if (autoDetectRef.current) clearInterval(autoDetectRef.current);
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    setUseWebcam(false);
  };

  const handleImageChange = (e) => {
    const selected = e.target.files[0];

    if (selected) {
      setFile(selected);
      setPreview(URL.createObjectURL(selected));
      setResult(null);
    }
  };

  const handleDetect = async () => {
    if (!file) {
      alert("Please select an image first.");
      return;
    }

    try {
      setLoading(true);

      const formData = new FormData();
      formData.append("image", file);

      const response = await API.post(
        "/detect-image",
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      setResult(response.data);
    } catch (error) {
      console.error("Detection Error:", error);

      if (error.response) {
        alert(JSON.stringify(error.response.data));
      } else {
        alert("Detection failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const hasViolation =
    result?.detections?.some(
      (item) =>
        item.class_id === 2 || // No Helmet
        item.class_id === 4 // No Vest
    ) || false;

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">
        Image Detection
      </h1>

      <div className="bg-white dark:bg-slate-800 p-6 rounded-xl shadow">
        <div className="flex flex-col xl:flex-row gap-4 mb-6">
          <div className="flex-1 flex flex-col gap-3">
             <label className="font-semibold dark:text-white">Upload File</label>
             <input
               type="file"
               accept="image/*"
               onChange={handleImageChange}
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
              disabled={loading || !file}
              className="bg-blue-600 text-white px-8 py-2 rounded-lg hover:bg-blue-700 w-full xl:w-auto h-10 disabled:opacity-50"
            >
              {loading ? "Detecting..." : "Detect PPE"}
            </button>
          </div>
        </div>

        {useWebcam && (
          <div className="mb-6 bg-gray-100 dark:bg-slate-700 p-4 rounded-xl flex flex-col items-center shadow-inner">
            <h3 className="font-semibold text-lg mb-3 dark:text-white flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
              Live CCTV Feed Processing
            </h3>
            <video ref={videoRef} autoPlay playsInline className="w-full max-w-2xl rounded-lg shadow-md bg-black border-2 border-gray-300 dark:border-slate-600" />
            <canvas ref={canvasRef} style={{ display: 'none' }} />
          </div>
        )}

        {preview && (
          <div className="mt-6">
            <h2 className="font-semibold mb-2">
              Image Preview
            </h2>

            <img
              src={preview}
              alt="preview"
              className="max-w-md rounded-lg border"
            />
          </div>
        )}

        {result && (
          <div className="mt-6 p-5 bg-gray-100 dark:bg-slate-700 rounded-lg border border-gray-200 dark:border-slate-600">
            <h2 className="font-bold text-xl mb-4 text-gray-800 dark:text-white">
              Detection Results
            </h2>

            {result.detections.length === 0 ? (
              <p className="text-gray-700 dark:text-gray-200">No objects detected.</p>
            ) : (
              <>
                <ul className="space-y-2 text-gray-700 dark:text-gray-200 mb-4">
                  {result.detections.map((item, index) => (
                    <li
                      key={index}
                      className="text-lg"
                    >
                      <strong>
                        {classNames[item.class_id]}
                      </strong>{" "}
                      ({(item.confidence * 100).toFixed(1)}%)
                    </li>
                  ))}
                </ul>

                <div
                  className={`mt-4 p-4 rounded-lg font-bold border ${
                    hasViolation
                      ? "bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-900/50"
                      : "bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-300 border-green-200 dark:border-green-900/50"
                  }`}
                >
                  {hasViolation ? "⚠️ VIOLATION DETECTED" : "✅ SAFE"}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ImageDetection;