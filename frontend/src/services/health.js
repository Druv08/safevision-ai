import { useCallback, useEffect, useState } from "react";
import API from "./api";

/**
 * GET /health. Returns { data, state, refresh } where state is
 * "checking" | "ok" | "degraded" | "offline". Polls when pollMs is set.
 */
export function useHealth(pollMs) {
  const [data, setData] = useState(null);
  const [state, setState] = useState("checking");

  const refresh = useCallback(() =>
    API.get("/health", { timeout: 8000 })
      .then((r) => { setData(r.data); setState(r.data.status === "ok" ? "ok" : "degraded"); })
      .catch(() => { setData(null); setState("offline"); }), []);

  useEffect(() => {
    refresh();
    if (!pollMs) return;
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  return { data, state, refresh };
}
