import { Routes, Route } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";

import Dashboard from "./pages/Dashboard";
import ImageDetection from "./pages/ImageDetection";
import VideoDetection from "./pages/VideoDetection";
import Violations from "./pages/Violations";
import About from "./pages/About";

function App() {
  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<Dashboard />} />

        <Route
          path="/image-detection"
          element={<ImageDetection />}
        />

        <Route
          path="/video-detection"
          element={<VideoDetection />}
        />

        <Route
          path="/violations"
          element={<Violations />}
        />

        <Route
          path="/about"
          element={<About />}
        />
      </Routes>
    </MainLayout>
  );
}

export default App;