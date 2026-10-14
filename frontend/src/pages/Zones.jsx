import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LuArrowLeft, LuRefreshCw, LuPlus, LuUndo2, LuCheck, LuX, LuTrash2, LuSave, LuImageOff } from "react-icons/lu";
import API, { apiError } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { POLICY, POLICY_OPTIONS } from "../theme";
import { PageHeader, Alert, EmptyState, Spinner, SectionTitle } from "../components/ui";

/* Zones are stored in normalised coordinates (0..1), so the snapshot's size does not matter. */
const pct = (v) => Math.round(v * 1000) / 1000;

function Zones() {
  const { id } = useParams();
  const { isAdmin } = useAuth();
  const toast = useToast();
  const [camera, setCamera] = useState(null);
  const [zones, setZones] = useState([]); // [{ name, policy, polygon }]
  const [dirty, setDirty] = useState(false);
  const [selected, setSelected] = useState(-1);
  const [draft, setDraft] = useState(null); // points being drawn, or null
  const [shot, setShot] = useState({ url: "", size: null, loading: true, error: "" });
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const svgRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([API.get(`/cameras/${id}`), API.get(`/cameras/${id}/zones`)])
      .then(([c, z]) => {
        if (cancelled) return;
        setCamera(c.data);
        setZones(z.data.map(({ name, policy, polygon }) => ({ name, policy, polygon })));
      })
      .catch((e) => !cancelled && setLoadError(apiError(e, "Could not load the camera.")));
    return () => { cancelled = true; };
  }, [id]);

  const loadSnapshot = useCallback(async () => {
    setShot((s) => ({ ...s, loading: true, error: "" }));
    try {
      const r = await API.get(`/cameras/${id}/snapshot`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      setShot((s) => { if (s.url) URL.revokeObjectURL(s.url); return { url, size: null, loading: false, error: "" }; });
    } catch (e) {
      // Error bodies arrive as a Blob because of responseType.
      let msg = apiError(e, "Could not get a frame from the camera.");
      try { msg = JSON.parse(await e.response.data.text()).detail || msg; } catch { /* keep msg */ }
      setShot((s) => ({ ...s, loading: false, error: msg }));
    }
  }, [id]);

  useEffect(() => {
    const t = setTimeout(loadSnapshot, 0);
    return () => clearTimeout(t);
  }, [loadSnapshot]);

  // Esc cancels the polygon being drawn.
  useEffect(() => {
    if (!draft) return;
    const onKey = (e) => { if (e.key === "Escape") setDraft(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [draft]);

  const change = (next) => { setZones(next); setDirty(true); };
  const update = (i, patch) => change(zones.map((z, k) => (k === i ? { ...z, ...patch } : z)));

  const pointFromEvent = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    return [pct(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))), pct(Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)))];
  };

  const finish = (points = draft) => {
    if (!points || points.length < 3) return;
    const next = [...zones, { name: `Zone ${zones.length + 1}`, policy: "both", polygon: points }];
    change(next);
    setSelected(next.length - 1);
    setDraft(null);
  };

  const onCanvasClick = (e) => {
    if (!draft) return;
    const p = pointFromEvent(e);
    // Clicking near the first point closes the polygon.
    if (draft.length >= 3 && shot.size) {
      const [fx, fy] = draft[0];
      const dx = (p[0] - fx) * shot.size.w, dy = (p[1] - fy) * shot.size.h;
      if (Math.hypot(dx, dy) < 0.02 * Math.max(shot.size.w, shot.size.h)) return finish();
    }
    // Functional update: clicks that arrive before the next render must not overwrite each other.
    setDraft((d) => (d ? [...d, p] : d));
  };

  const save = async () => {
    setSaving(true);
    try {
      const r = await API.put(`/cameras/${id}/zones`, { zones });
      setZones(r.data.map(({ name, policy, polygon }) => ({ name, policy, polygon })));
      setDirty(false);
      toast(camera?.status?.state === "running" ? "Zones saved. They apply from the next frame." : "Zones saved.");
    } catch (e) {
      toast(apiError(e, "Could not save the zones."), "danger");
    } finally {
      setSaving(false);
    }
  };

  if (loadError) {
    return (
      <div>
        <Link to="/cameras" className="btn btn-ghost btn-sm mb-4"><LuArrowLeft /> Cameras</Link>
        <Alert>{loadError}</Alert>
      </div>
    );
  }
  if (!camera) return <div className="card p-10 flex justify-center"><Spinner /></div>;

  const W = shot.size?.w || 1, H = shot.size?.h || 1;
  const toPx = (poly) => poly.map(([x, y]) => `${x * W},${y * H}`).join(" ");
  const stroke = Math.max(2, W / 400);

  return (
    <div>
      <Link to="/cameras" className="btn btn-ghost btn-sm mb-3 -ml-2"><LuArrowLeft /> Cameras</Link>
      <PageHeader
        title={`Zones · ${camera.name}`}
        description="Draw areas on the camera image and choose what each one requires. A person counts as inside a zone when their feet are inside it."
        actions={isAdmin && (
          <>
            {dirty && <span className="badge tone-warning"><span className="dot" />Unsaved changes</span>}
            <button className="btn btn-primary" onClick={save} disabled={!dirty || saving || Boolean(draft)}>
              {saving ? <Spinner /> : <LuSave />} Save zones
            </button>
          </>
        )}
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <section className="card overflow-hidden xl:col-span-2 min-w-0" aria-label="Camera image with zones">
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-line">
            {isAdmin && !draft && (
              <button className="btn btn-secondary btn-sm" onClick={() => { setDraft([]); setSelected(-1); }} disabled={!shot.size}>
                <LuPlus /> Draw zone
              </button>
            )}
            {draft && (
              <>
                <span className="text-sm text-muted mr-auto">
                  {draft.length < 3 ? `Click to add points (${draft.length} so far, 3 needed).` : "Click the first point or Finish to close the zone."}
                </span>
                <button className="btn btn-ghost btn-sm" onClick={() => setDraft(draft.slice(0, -1))} disabled={!draft.length}><LuUndo2 /> Undo</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setDraft(null)}><LuX /> Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={() => finish()} disabled={draft.length < 3}><LuCheck /> Finish</button>
              </>
            )}
            {!draft && (
              <button className="btn btn-ghost btn-sm ml-auto" onClick={loadSnapshot} disabled={shot.loading}>
                {shot.loading ? <Spinner /> : <LuRefreshCw />} New snapshot
              </button>
            )}
          </div>

          <div className="relative bg-black">
            {shot.url ? (
              <div className="relative">
                <img
                  src={shot.url}
                  alt={`Snapshot from ${camera.name}`}
                  className="block w-full h-auto select-none"
                  draggable={false}
                  onLoad={(e) => setShot((s) => ({ ...s, size: { w: e.target.naturalWidth, h: e.target.naturalHeight } }))}
                />
                {shot.size && (
                  <svg
                    ref={svgRef}
                    viewBox={`0 0 ${W} ${H}`}
                    className={`absolute inset-0 w-full h-full ${draft ? "cursor-crosshair" : ""}`}
                    onClick={onCanvasClick}
                    role="img"
                    aria-label={`${zones.length} zone${zones.length === 1 ? "" : "s"} drawn on the camera image`}
                  >
                    {zones.map((z, i) => (
                      <polygon
                        key={i}
                        points={toPx(z.polygon)}
                        style={{ fill: POLICY[z.policy].color, stroke: POLICY[z.policy].color }}
                        fillOpacity={i === selected ? 0.3 : 0.15}
                        strokeWidth={i === selected ? stroke * 1.8 : stroke}
                        strokeDasharray={z.policy === "no_entry" ? `${stroke * 4} ${stroke * 2}` : undefined}
                        onClick={(e) => { if (!draft) { e.stopPropagation(); setSelected(i); } }}
                        className={draft ? "" : "cursor-pointer"}
                      />
                    ))}
                    {draft && draft.length > 0 && (
                      <>
                        <polyline points={toPx(draft)} fill="none" stroke="white" strokeWidth={stroke} strokeDasharray={`${stroke * 3} ${stroke * 2}`} />
                        {draft.map(([x, y], k) => (
                          <circle key={k} cx={x * W} cy={y * H} r={stroke * (k === 0 ? 3 : 2)} style={{ fill: k === 0 ? "var(--primary)" : "white" }} />
                        ))}
                      </>
                    )}
                  </svg>
                )}
              </div>
            ) : (
              <div className="aspect-video flex items-center justify-center p-6">
                {shot.loading ? (
                  <p className="text-sm text-white/80 flex items-center gap-2"><Spinner /> Getting a frame from the camera…</p>
                ) : (
                  <EmptyState icon={LuImageOff} title="No camera image" className="text-white"
                    action={<button className="btn btn-primary" onClick={loadSnapshot}><LuRefreshCw /> Try again</button>}>
                    {shot.error}
                  </EmptyState>
                )}
              </div>
            )}
          </div>
        </section>

        <section className="card p-4 sm:p-5 min-w-0" aria-label="Zone list">
          <SectionTitle title="Zones" description={`Outside all zones: ${POLICY[camera.default_policy]?.label}. Change this in the camera settings.`} />
          {zones.length === 0 ? (
            <p className="text-sm text-muted">No zones yet. {isAdmin ? "Use Draw zone and click on the image." : ""}</p>
          ) : (
            <ul className="space-y-2">
              {zones.map((z, i) => (
                <li key={i} className={`rounded-lg border p-3 space-y-2 ${i === selected ? "border-primary/60 bg-primary/5" : "border-line"}`}
                  onClick={() => setSelected(i)}>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: POLICY[z.policy].color }} aria-hidden="true" />
                    <input className="input h-8" aria-label="Zone name" maxLength={100} value={z.name} disabled={!isAdmin}
                      onChange={(e) => update(i, { name: e.target.value })} />
                    {isAdmin && (
                      <button className="btn btn-ghost btn-sm btn-icon" aria-label={`Delete ${z.name}`}
                        onClick={(e) => { e.stopPropagation(); change(zones.filter((_, k) => k !== i)); setSelected(-1); }}>
                        <LuTrash2 />
                      </button>
                    )}
                  </div>
                  <select className="input h-8" aria-label={`Rule for ${z.name}`} value={z.policy} disabled={!isAdmin}
                    onChange={(e) => update(i, { policy: e.target.value })}>
                    {POLICY_OPTIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                  </select>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-5 text-xs text-muted space-y-1.5">
            <p><strong className="text-fg font-medium">No PPE required:</strong> a bare head here is not a violation.</p>
            <p><strong className="text-fg font-medium">No entry:</strong> anyone standing here for 2 s is a zone intrusion.</p>
            <p>Where zones overlap, all their requirements apply.</p>
          </div>
        </section>
      </div>
    </div>
  );
}

export default Zones;
