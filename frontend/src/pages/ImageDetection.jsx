import { useState } from "react";
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

      <div className="bg-white p-6 rounded-xl shadow">
        <div className="flex items-center gap-3 mb-4">
          <input
            type="file"
            accept="image/*"
            onChange={handleImageChange}
          />

          <button
            onClick={handleDetect}
            disabled={loading}
            className="bg-blue-600 text-white px-5 py-2 rounded-lg hover:bg-blue-700"
          >
            {loading ? "Detecting..." : "Detect PPE"}
          </button>
        </div>

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
          <div className="mt-6 p-4 bg-gray-100 rounded-lg">
            <h2 className="font-bold text-xl mb-4">
              Detection Results
            </h2>

            {result.detections.length === 0 ? (
              <p>No objects detected.</p>
            ) : (
              <>
                <ul>
                  {result.detections.map((item, index) => (
                    <li
                      key={index}
                      style={{
                        marginBottom: "10px",
                        fontSize: "18px",
                      }}
                    >
                      <strong>
                        {classNames[item.class_id]}
                      </strong>{" "}
                      ({(item.confidence * 100).toFixed(1)}%)
                    </li>
                  ))}
                </ul>

                <div
                  style={{
                    marginTop: "20px",
                    padding: "12px",
                    borderRadius: "8px",
                    fontWeight: "bold",
                    backgroundColor: hasViolation
                      ? "#ffe5e5"
                      : "#e7ffe7",
                    color: hasViolation
                      ? "#c62828"
                      : "#2e7d32",
                  }}
                >
                  {hasViolation
                    ? "⚠ VIOLATION DETECTED"
                    : "✅ SAFE"}
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