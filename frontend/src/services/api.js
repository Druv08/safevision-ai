import axios from "axios";
import { supabase } from "./supabase";

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
});

// Send the Supabase access token on every request.
API.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// An expired or revoked session: sign out so ProtectedRoute sends the user to /login.
API.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) await supabase.auth.signOut();
    return Promise.reject(err);
  },
);

export default API;

/** axios error -> readable message. FastAPI puts it in `detail` (string, or a list for 422s). */
export function apiError(e, fallback) {
  if (e?.code === "ERR_CANCELED") return "Cancelled.";
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  if (e?.response?.status === 429) return "Too many requests. Wait a moment and try again.";
  if (e?.response) return `${fallback} (HTTP ${e.response.status})`;
  if (e?.code === "ERR_NETWORK") return "Cannot reach the backend. Check that it is running.";
  return fallback;
}

// Matches the backend's MAX_UPLOAD_MB default; the server still enforces its own limit.
export const MAX_UPLOAD_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB || 50);
