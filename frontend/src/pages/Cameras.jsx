import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  LuPlus, LuPlay, LuSquare, LuPencil, LuTrash2, LuShapes, LuCctv, LuKeyRound, LuRefreshCw,
} from "react-icons/lu";
import API, { apiError } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { CAMERA_STATE, POLICY, POLICY_OPTIONS } from "../theme";
import { PageHeader, Alert, EmptyState, Dialog, ConfirmDialog, Spinner } from "../components/ui";

const POLL_MS = 3000;
const DEFAULT_POLICIES = POLICY_OPTIONS.filter((p) => p.value !== "no_entry");

const ago = (iso) => {
  if (!iso) return "never";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : new Date(iso).toLocaleString();
};

function Cameras() {
  const { isAdmin } = useAuth();
  const toast = useToast();
  const [cameras, setCameras] = useState(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null); // null | {} (new) | camera
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(""); // camera id with an action in flight

  const load = useCallback(async () => {
    try {
      const r = await API.get("/cameras");
      setCameras(r.data);
      setError("");
    } catch (e) {
      setError(apiError(e, "Could not load cameras."));
    }
  }, []);

  useEffect(() => {
    // Polled for live status; the first call fills the list.
    const first = setTimeout(load, 0);
    const id = setInterval(load, POLL_MS);
    return () => { clearTimeout(first); clearInterval(id); };
  }, [load]);

  const act = async (camera, action) => {
    setBusy(camera.id);
    try {
      await API.post(`/cameras/${camera.id}/${action}`);
      toast(action === "start" ? `${camera.name} is starting.` : `${camera.name} stopped.`);
      load();
    } catch (e) {
      toast(apiError(e, `Could not ${action} the camera.`), "danger");
    } finally {
      setBusy("");
    }
  };

  const remove = async () => {
    setBusy(deleting.id);
    try {
      await API.delete(`/cameras/${deleting.id}`);
      toast(`${deleting.name} deleted.`);
      setDeleting(null);
      load();
    } catch (e) {
      toast(apiError(e, "Could not delete the camera."), "danger");
    } finally {
      setBusy("");
    }
  };

  return (
    <div>
      <PageHeader
        title="Cameras"
        description="Network cameras (RTSP) analysed continuously on the server. Each camera can have zones with their own PPE rules."
        actions={
          <>
            <button className="btn btn-ghost btn-icon" onClick={load} aria-label="Refresh" data-tip="Refresh"><LuRefreshCw /></button>
            {isAdmin && <button className="btn btn-primary" onClick={() => setEditing({})}><LuPlus /> Add camera</button>}
          </>
        }
      />

      {error && <Alert className="mb-4" onRetry={load}>{error}</Alert>}

      {cameras === null && !error ? (
        <div className="card p-10 flex justify-center"><Spinner /></div>
      ) : cameras?.length === 0 ? (
        <div className="card p-6">
          <EmptyState
            icon={LuCctv}
            title="No cameras yet"
            action={isAdmin && <button className="btn btn-primary" onClick={() => setEditing({})}><LuPlus /> Add camera</button>}
          >
            Add an RTSP camera, for example <code className="font-mono text-xs">rtsp://192.168.1.20:554/stream1</code>.
          </EmptyState>
        </div>
      ) : (
        <ul className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {(cameras || []).map((c) => {
            const st = c.status || { state: "stopped" };
            const meta = CAMERA_STATE[st.state] || CAMERA_STATE.stopped;
            const active = st.state !== "stopped";
            return (
              <li key={c.id} className="card p-4 sm:p-5 flex flex-col gap-3 min-w-0">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <h2 className="font-semibold text-fg truncate">{c.name}</h2>
                    <p className="text-xs text-muted font-mono truncate mt-0.5" title={c.url}>
                      {c.url}
                      {c.has_credentials && <LuKeyRound className="inline ml-1.5 -mt-0.5" aria-label="Credentials saved" />}
                    </p>
                  </div>
                  <span className={`badge ${meta.tone} flex-shrink-0`} role="status">
                    <span className={`dot ${st.state === "running" ? "animate-live" : ""}`} />{meta.label}
                  </span>
                </div>

                <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 text-sm">
                  <div><dt className="text-xs text-muted">Analysed</dt><dd className="tabular-nums">{active ? `${st.analyzed_fps} / ${c.sample_fps} fps` : `${c.sample_fps} fps`}</dd></div>
                  <div><dt className="text-xs text-muted">Last frame</dt><dd>{ago(st.last_frame_at)}</dd></div>
                  <div><dt className="text-xs text-muted">Alerts</dt><dd className="tabular-nums">{st.alerts ?? 0}</dd></div>
                  <div><dt className="text-xs text-muted">Reconnects</dt><dd className="tabular-nums">{st.reconnects ?? 0}</dd></div>
                  <div className="col-span-2 sm:col-span-4"><dt className="text-xs text-muted">Outside zones</dt><dd>{POLICY[c.default_policy]?.label}</dd></div>
                </dl>

                {st.last_error && st.state !== "running" && (
                  <Alert tone={st.state === "error" ? "danger" : "warning"}>{st.last_error}</Alert>
                )}
                {st.persist_errors > 0 && (
                  <Alert tone="warning">{st.persist_errors} result(s) could not be saved. Check the database connection.</Alert>
                )}

                <div className="flex flex-wrap gap-2 mt-auto pt-1">
                  {isAdmin && (active ? (
                    <button className="btn btn-secondary btn-sm" onClick={() => act(c, "stop")} disabled={busy === c.id}>
                      <LuSquare /> Stop
                    </button>
                  ) : (
                    <button className="btn btn-primary btn-sm" onClick={() => act(c, "start")} disabled={busy === c.id}>
                      {busy === c.id ? <Spinner /> : <LuPlay />} Start
                    </button>
                  ))}
                  <Link className="btn btn-secondary btn-sm" to={`/cameras/${c.id}/zones`}><LuShapes /> Zones</Link>
                  {isAdmin && (
                    <>
                      <button className="btn btn-ghost btn-sm" onClick={() => setEditing(c)}><LuPencil /> Edit</button>
                      <button className="btn btn-ghost btn-sm ml-auto" onClick={() => setDeleting(c)} aria-label={`Delete ${c.name}`}><LuTrash2 /></button>
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {editing && <CameraDialog camera={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
      <ConfirmDialog
        open={Boolean(deleting)}
        title={`Delete ${deleting?.name}?`}
        confirmLabel="Delete camera"
        danger
        busy={busy === deleting?.id}
        onConfirm={remove}
        onCancel={() => setDeleting(null)}
      >
        The camera stops and its zones are deleted. Violations it logged are kept.
      </ConfirmDialog>
    </div>
  );
}

function CameraDialog({ camera, onClose, onSaved }) {
  const toast = useToast();
  const isNew = !camera.id;
  const [form, setForm] = useState({
    name: camera.name || "",
    url: camera.url || "",
    username: "",
    password: "",
    clear_credentials: false,
    sample_fps: camera.sample_fps ?? 5,
    default_policy: camera.default_policy || "both",
    enabled: true,
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    // Credentials are write-only: send them only when typed.
    const body = {
      name: form.name.trim(),
      url: form.url.trim(),
      sample_fps: Number(form.sample_fps),
      default_policy: form.default_policy,
      ...(form.username && { username: form.username }),
      ...(form.password && { password: form.password }),
    };
    try {
      if (isNew) await API.post("/cameras", { ...body, enabled: form.enabled });
      else await API.patch(`/cameras/${camera.id}`, { ...body, clear_credentials: form.clear_credentials });
      toast(isNew ? "Camera added." : "Camera updated.");
      onSaved();
    } catch (err) {
      setError(apiError(err, "Could not save the camera."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={isNew ? "Add camera" : `Edit ${camera.name}`}
      description="Credentials are encrypted on the server and never shown again."
      width="34rem"
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" type="submit" form="camera-form" disabled={saving}>
            {saving && <Spinner />} {isNew ? "Add camera" : "Save"}
          </button>
        </>
      }
    >
      <form id="camera-form" onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="label">Name</span>
          <input className="input" required maxLength={100} value={form.name} onChange={set("name")} placeholder="North gate" />
        </label>
        <label className="block">
          <span className="label">Stream URL</span>
          <input className="input font-mono" required maxLength={2000} value={form.url} onChange={set("url")} placeholder="rtsp://192.168.1.20:554/stream1" spellCheck={false} />
          <span className="block text-xs text-muted mt-1">RTSP over TCP. Credentials in the URL are moved to encrypted storage.</span>
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="label">Username</span>
            <input className="input" autoComplete="off" maxLength={200} value={form.username} onChange={set("username")}
              placeholder={!isNew && camera.has_credentials ? "Unchanged" : "Optional"} disabled={form.clear_credentials} />
          </label>
          <label className="block">
            <span className="label">Password</span>
            <input className="input" type="password" autoComplete="new-password" maxLength={200} value={form.password} onChange={set("password")}
              placeholder={!isNew && camera.has_credentials ? "Unchanged" : "Optional"} disabled={form.clear_credentials} />
          </label>
        </div>
        {!isNew && camera.has_credentials && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.clear_credentials} onChange={set("clear_credentials")} className="accent-[var(--primary)]" />
            Remove the saved credentials
          </label>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="label">Frames analysed per second</span>
            <input className="input" type="number" min="0.5" max="30" step="0.5" required value={form.sample_fps} onChange={set("sample_fps")} />
          </label>
          <label className="block">
            <span className="label">Rule outside zones</span>
            <select className="input" value={form.default_policy} onChange={set("default_policy")}>
              {DEFAULT_POLICIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </label>
        </div>
        {isNew && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.enabled} onChange={set("enabled")} className="accent-[var(--primary)]" />
            Start analysing now (and after every backend restart)
          </label>
        )}
        {error && <Alert>{error}</Alert>}
      </form>
    </Dialog>
  );
}

export default Cameras;
