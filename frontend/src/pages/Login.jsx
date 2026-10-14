import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Logo, Alert, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";

function Login() {
  const { session, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (session) return <Navigate to={from} replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const { error: err } = await signIn(email, password);
    setBusy(false);
    if (err) setError(err.message);
    else navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-canvas">
      <Link to="/" className="mb-8 rounded-md" aria-label="SafeVisionAI home"><Logo /></Link>
      <form onSubmit={handleSubmit} className="card p-6 sm:p-8 w-full max-w-sm space-y-5" noValidate={false}>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
          <p className="text-sm text-muted mt-1">Accounts are created by your administrator.</p>
        </div>

        <label className="block">
          <span className="label">Email</span>
          <input type="email" required autoComplete="email" autoFocus value={email}
            onChange={(e) => setEmail(e.target.value)} className="input" />
        </label>

        <label className="block">
          <span className="label">Password</span>
          <input type="password" required autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} className="input" />
        </label>

        {error && <Alert>{error}</Alert>}

        <button type="submit" disabled={busy} className="btn btn-primary w-full">
          {busy && <Spinner />} {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <Link to="/" className="mt-6 text-sm text-muted hover:text-fg">Back to home</Link>
    </div>
  );
}

export default Login;
