import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AUTH_DISABLED } from "./context/AuthContext";
import MainLayout from "./layouts/MainLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import { PageFallback } from "./components/ui";

// Route-level code splitting: the dashboard's chart library only loads when needed.
const Landing = lazy(() => import("./pages/Landing"));
const Login = lazy(() => import("./pages/Login"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const ImageDetection = lazy(() => import("./pages/ImageDetection"));
const VideoDetection = lazy(() => import("./pages/VideoDetection"));
const LiveMonitoring = lazy(() => import("./pages/LiveMonitoring"));
const Cameras = lazy(() => import("./pages/Cameras"));
const Zones = lazy(() => import("./pages/Zones"));
const Alerts = lazy(() => import("./pages/Alerts"));
const Violations = lazy(() => import("./pages/Violations"));
const About = lazy(() => import("./pages/About"));

function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={AUTH_DISABLED ? <Navigate to="/dashboard" replace /> : <Login />} />

        <Route element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/image-detection" element={<ImageDetection />} />
          <Route path="/video-detection" element={<VideoDetection />} />
          <Route path="/live" element={<LiveMonitoring />} />
          <Route path="/cameras" element={<Cameras />} />
          <Route path="/cameras/:id/zones" element={<Zones />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/violations" element={<Violations />} />
          <Route path="/about" element={<About />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default App;
