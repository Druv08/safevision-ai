/* Shared presentation metadata. Colours live as CSS tokens in index.css;
   this file maps domain values (severity, status, detection class) onto them. */

export const SEVERITY_TONE = { Critical: "tone-danger", High: "tone-danger", Medium: "tone-warning" };

export const STATUS_META = {
  new:          { label: "Awaiting review", tone: "tone-warning" },
  acknowledged: { label: "Acknowledged",    tone: "tone-info" },
  action_taken: { label: "Action taken",    tone: "tone-ok" },
  closed:       { label: "Closed",          tone: "tone-neutral" },
};

// Why it happened, chosen by the reviewer (backend CAUSES). "PPE not issued" is the site's gap, not the worker's.
export const CAUSE_OPTIONS = [
  { value: "ppe_not_issued",  label: "PPE not issued" },
  { value: "ppe_not_worn",    label: "PPE issued, not worn" },
  { value: "ppe_damaged",     label: "PPE damaged or unsuitable" },
  { value: "false_detection", label: "False detection" },
  { value: "other",           label: "Other" },
];
export const CAUSE_LABEL = Object.fromEntries(CAUSE_OPTIONS.map((c) => [c.value, c.label]));

export const SOURCE_LABEL = { image: "Image upload", video: "Video upload", camera: "Camera" };

export const TYPE_OPTIONS = [
  { value: "no_helmet", label: "Helmet missing" },
  { value: "no_vest",   label: "Safety vest missing" },
  { value: "zone_intrusion", label: "Zone intrusion" },
];
export const TYPE_LABEL = Object.fromEntries(TYPE_OPTIONS.map((t) => [t.value, t.label]));

// Zone policies (backend/services/zones.py). `color` is a CSS token for the zone outline.
export const POLICY_OPTIONS = [
  { value: "both",     label: "Hard hat and vest", color: "var(--primary)" },
  { value: "helmet",   label: "Hard hat only",     color: "var(--info)" },
  { value: "vest",     label: "Vest only",         color: "var(--warning)" },
  { value: "none",     label: "No PPE required",   color: "var(--muted)" },
  { value: "no_entry", label: "No entry",          color: "var(--danger)" },
];
export const POLICY = Object.fromEntries(POLICY_OPTIONS.map((p) => [p.value, p]));

// Stream worker states (backend/services/stream_service.py).
export const CAMERA_STATE = {
  running:      { label: "Streaming",    tone: "tone-ok" },
  connecting:   { label: "Connecting",   tone: "tone-info" },
  reconnecting: { label: "Reconnecting", tone: "tone-warning" },
  error:        { label: "Error",        tone: "tone-danger" },
  stopped:      { label: "Stopped",      tone: "tone-neutral" },
};

// Detection classes returned by /detect-image (`class_id`).
export const DETECTION_CLASSES = {
  0: { label: "Person",    tone: "tone-info",    violation: false },
  1: { label: "Hard hat",  tone: "tone-ok",      violation: false },
  2: { label: "No hard hat", tone: "tone-danger", violation: true },
  3: { label: "Vest",      tone: "tone-ok",      violation: false },
  4: { label: "No vest",   tone: "tone-danger",  violation: true },
};

/* Recharts needs concrete colour values, so read the live tokens.
   Call again after a theme change. */
export function chartTheme() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  return {
    helmet: v("--danger"),
    vest: v("--warning"),
    intrusion: v("--info"),
    primary: v("--primary"),
    info: v("--info"),
    grid: v("--line"),
    axis: { fill: v("--muted"), fontSize: 12 },
    cursor: { fill: v("--surface-2") },
    tooltip: {
      backgroundColor: v("--surface"),
      border: `1px solid ${v("--line")}`,
      borderRadius: 8,
      color: v("--fg"),
      fontSize: 12,
      boxShadow: "0 12px 32px -12px rgba(0,0,0,0.5)",
    },
  };
}
