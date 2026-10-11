/* Shared presentation metadata. Colours live as CSS tokens in index.css;
   this file maps domain values (severity, status, detection class) onto them. */

export const SEVERITY_TONE = { Critical: "tone-danger", High: "tone-danger", Medium: "tone-warning" };

export const STATUS_META = {
  new:          { label: "Awaiting review", tone: "tone-warning" },
  acknowledged: { label: "Acknowledged",    tone: "tone-info" },
  closed:       { label: "Closed",          tone: "tone-ok" },
};

export const SOURCE_LABEL = { image: "Image upload", video: "Video upload", camera: "Live camera" };

export const TYPE_OPTIONS = [
  { value: "no_helmet", label: "Helmet missing" },
  { value: "no_vest",   label: "Safety vest missing" },
];

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
