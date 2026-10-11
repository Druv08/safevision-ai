import { LuRefreshCw, LuHardHat, LuShirt, LuUser, LuCircleCheck, LuCircleMinus } from "react-icons/lu";
import { useHealth } from "../services/health";
import { PageHeader, SectionTitle, Alert } from "../components/ui";

const PIPELINE = [
  ["Capture", "An uploaded image, every frame of an uploaded video, or a frame or clip from a live browser camera."],
  ["Detect", "Three YOLOv8 models run on each frame: a 5-class PPE model (vests), a construction-safety model (hard hats) and COCO YOLOv8n (people)."],
  ["Verify", "A missing hard hat or vest is a violation only when it overlaps a detected person, at most once per person and type. A helmet held in the hand counts as missing."],
  ["Record", "Each violation is stored with a screenshot. Viewers review and export; admins acknowledge, close or delete. Evidence views, exports and changes are audit-logged."],
];

const PPE = [
  { icon: LuHardHat, label: "Hard hats", supported: true, text: "Detected and checked for being worn on the head." },
  { icon: LuShirt, label: "High-visibility vests", supported: true, text: "Detected and matched to each worker." },
  { icon: LuUser, label: "People", supported: true, text: "Used to attribute PPE to individual workers." },
  { icon: null, label: "Gloves, goggles, boots, harnesses", supported: false, text: "Not detected by the current models." },
];

const STACK = [
  ["Frontend", "React 19, Vite, Tailwind CSS 4, Recharts"],
  ["Backend", "FastAPI (Python), OpenCV"],
  ["Models", "Ultralytics YOLOv8 (three models per frame)"],
  ["Data & auth", "Supabase Postgres with row-level security, private Storage bucket, Supabase Auth"],
];

const LIMITS = [
  "Network cameras (RTSP / IP) are not supported yet. Live monitoring uses a camera attached to the browser.",
  "There are no automatic alerts or notifications. Violations are reviewed on the Violations page.",
  "Detection quality depends on camera angle, distance and lighting. Review each violation before acting on it.",
];

function About() {
  const { data, state, refresh } = useHealth();
  const model = data?.model;
  const db = data?.database;

  const rows = data && [
    ["Overall", data.status === "ok" ? "Operational" : "Degraded", data.status === "ok" ? "tone-ok" : "tone-warning"],
    ["Backend API", "Online", "tone-ok"],
    ["Detection models", model?.loaded ? "Loaded" : "Not loaded", model?.loaded ? "tone-ok" : "tone-danger"],
    ["Database", db?.mode === "local" ? "Local development store" : db?.connected ? "Supabase connected" : "Unreachable",
      db?.connected ? (db?.mode === "local" ? "tone-warning" : "tone-ok") : "tone-danger"],
    ["Disk space", `${(data.disk?.free_mb / 1024).toFixed(1)} GB free`, data.disk?.ok ? "tone-ok" : "tone-warning"],
  ];

  return (
    <div>
      <PageHeader
        title="About & System"
        description="SafeVisionAI checks images, video and live camera frames for missing hard hats and high-visibility vests, and keeps every violation with evidence for review."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="card p-4 sm:p-5 lg:col-span-1" aria-label="System status">
          <SectionTitle
            title="System status"
            description="Live from the backend health check"
            action={<button onClick={refresh} className="btn btn-ghost btn-sm btn-icon" aria-label="Refresh status" data-tip="Refresh" data-tip-align="end"><LuRefreshCw /></button>}
          />
          {state === "checking" ? (
            <div className="space-y-3">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-6" />)}</div>
          ) : state === "offline" ? (
            <Alert onRetry={refresh} title="Backend unreachable">Detection, violations and exports are unavailable until it is back.</Alert>
          ) : (
            <>
              <ul className="divide-y divide-line">
                {rows.map(([label, value, tone]) => (
                  <li key={label} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 text-sm">
                    <span className="text-muted">{label}</span>
                    <span className={`badge ${tone}`}><span className="dot" />{value}</span>
                  </li>
                ))}
              </ul>
              {model?.version && (
                <div className="mt-3 rounded-lg bg-surface-2/60 border border-line px-3 py-2">
                  <p className="text-xs text-muted">Model version</p>
                  <p className="font-mono text-xs break-all mt-0.5">{model.version}</p>
                </div>
              )}
              {model?.error && <Alert className="mt-3" tone="warning">{model.error}</Alert>}
            </>
          )}
        </section>

        <section className="card p-4 sm:p-5 lg:col-span-2" aria-label="Detection pipeline">
          <SectionTitle title="How detection works" />
          <ol className="grid sm:grid-cols-2 gap-3">
            {PIPELINE.map(([title, text], i) => (
              <li key={title} className="rounded-lg border border-line bg-surface-2/40 p-4">
                <p className="text-xs font-semibold text-primary tabular-nums">Step {i + 1}</p>
                <p className="font-medium mt-1">{title}</p>
                <p className="text-sm text-muted mt-1">{text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="card p-4 sm:p-5" aria-label="PPE coverage">
          <SectionTitle title="PPE coverage" />
          <ul className="space-y-3">
            {PPE.map(({ icon: Icon, label, supported, text }) => (
              <li key={label} className="flex gap-3 text-sm">
                {supported ? <LuCircleCheck className="text-primary mt-0.5 flex-shrink-0" aria-label="Supported" /> : <LuCircleMinus className="text-subtle mt-0.5 flex-shrink-0" aria-label="Not supported" />}
                <div>
                  <p className="font-medium flex items-center gap-1.5">{Icon && <Icon className="text-muted" aria-hidden="true" />}{label}</p>
                  <p className="text-muted">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="card p-4 sm:p-5" aria-label="Technology">
          <SectionTitle title="Technology" />
          <dl className="space-y-3 text-sm">
            {STACK.map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-muted">{k}</dt>
                <dd className="mt-0.5">{v}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="card p-4 sm:p-5" aria-label="Known limitations">
          <SectionTitle title="Known limitations" />
          <ul className="space-y-3 text-sm text-muted list-disc pl-4 marker:text-subtle">
            {LIMITS.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </section>
      </div>
    </div>
  );
}

export default About;
