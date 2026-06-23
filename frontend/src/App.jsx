import { Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";

import MainLayout from "./layouts/MainLayout";

import Dashboard from "./pages/Dashboard";
import ImageDetection from "./pages/ImageDetection";
import VideoDetection from "./pages/VideoDetection";
import Violations from "./pages/Violations";
import About from "./pages/About";

function App() {
  return (
    <Routes>
      {/* Landing Page without Layout */}
      <Route path="/" element={<Landing />} />

      {/* Dashboard Routes with Layout */}
      <Route
        path="/dashboard"
        element={
          <MainLayout>
            <Dashboard />
          </MainLayout>
        }
      />
      <Route
        path="/image-detection"
        element={
          <MainLayout>
            <ImageDetection />
          </MainLayout>
        }
      />
      <Route
        path="/video-detection"
        element={
          <MainLayout>
            <VideoDetection />
          </MainLayout>
        }
      />
      <Route
        path="/violations"
        element={
          <MainLayout>
            <Violations />
          </MainLayout>
        }
      />
      <Route
        path="/about"
        element={
          <MainLayout>
            <About />
          </MainLayout>
        }
      />
    </Routes>
  );
}

export default App;