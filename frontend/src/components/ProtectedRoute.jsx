import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Spinner } from "./ui";

function ProtectedRoute({ children }) {
  const { session, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted text-2xl" role="status" aria-label="Checking your session">
        <Spinner />
      </div>
    );
  }
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return children;
}

export default ProtectedRoute;
