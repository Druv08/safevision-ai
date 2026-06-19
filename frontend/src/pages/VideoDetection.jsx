import { useState } from "react";
import API from "../services/api";

function VideoDetection() {
  const [video, setVideo] = useState(null);
  const [videoName, setVideoName] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

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

      <div className="bg-white p-6 rounded-xl shadow">
        <div className="flex items-center gap-3 mb-4">
          <input
            type="file"
            accept="video/*"
            onChange={handleVideoChange}
          />

          <button
            onClick={handleDetect}
            disabled={loading}
            className="bg-blue-600 text-white px-5 py-2 rounded-lg hover:bg-blue-700"
          >
            {loading ? "Processing..." : "Detect PPE"}
          </button>
        </div>

        {videoName && (
          <div className="mt-4">
            <strong>Selected Video:</strong> {videoName}
          </div>
        )}

        {result && (
  <div className="mt-6 p-5 bg-gray-100 rounded-lg">

    <h2 className="text-xl font-bold mb-4">
      Video Analysis Results
    </h2>

    <div className="space-y-3">

      <p>
        <strong>Filename:</strong>{" "}
        {result.filename}
      </p>

      <p>
        <strong>Status:</strong>{" "}
        <span className="text-green-600 font-semibold">
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