/* ══════════════════════════════════════════════════════════════
   SafeVisionAI — shared palette
   Single source of truth for the industrial green/gold theme used
   by the landing page and every dashboard page.
   ══════════════════════════════════════════════════════════════ */

/* Core brand */
export const GOLD = "#E2A442";
export const GOLD_SOFT = "#F3CE86";
export const DEEP = "#1B4436";
export const MOSS = "#27604B";
export const ABYSS = "#08150F";
export const CREAM = "#F7F0EB";

/* Data / status accents — kept inside the green-gold world so
   charts and badges never reintroduce the old blue-slate palette. */
export const OK = "#5FD08A";
export const WARN = "#E2A442";
export const ALERT = "#F2593F";
export const HIGH = "#E8763F";

/* Two-series chart palette: vest vs helmet violations.
   Recharts takes concrete values rather than CSS classes, so the
   chart chrome is built per theme instead of via tokens. */
export const CHART_COLORS = [WARN, ALERT];

const CHART_THEME = {
  dark: {
    axis: "rgba(247,240,235,0.45)",
    legend: "rgba(247,240,235,0.55)",
    cursor: "rgba(247,240,235,0.05)",
    cellStroke: "#0E2419",
    tooltipBg: "#0E2419",
    tooltipBorder: "rgba(247,240,235,0.12)",
    tooltipFg: CREAM,
    tooltipShadow: "0 18px 45px -12px rgba(0,0,0,0.8)",
  },
  light: {
    axis: "rgba(16,35,26,0.55)",
    legend: "rgba(16,35,26,0.68)",
    cursor: "rgba(27,68,54,0.07)",
    cellStroke: "#FBF7F2",
    tooltipBg: "#FBF7F2",
    tooltipBorder: "rgba(27,68,54,0.18)",
    tooltipFg: "#10231A",
    tooltipShadow: "0 18px 45px -14px rgba(27,68,54,0.35)",
  },
};

export function chartStyles(theme = "dark") {
  const t = CHART_THEME[theme] ?? CHART_THEME.dark;
  return {
    axis: { fill: t.axis, fontSize: 11 },
    cursor: { fill: t.cursor },
    cellStroke: t.cellStroke,
    legend: { color: t.legend, fontSize: "12px", paddingTop: "12px" },
    tooltip: {
      backgroundColor: t.tooltipBg,
      border: `1px solid ${t.tooltipBorder}`,
      color: t.tooltipFg,
      borderRadius: "12px",
      boxShadow: t.tooltipShadow,
    },
  };
}

/* Severity badges — graded through gold into alert red.
   Token-driven so they re-colour with the theme. */
export const SEVERITY_STYLES = {
  Critical: "sev-critical sv-tone-strong sv-tone-ink",
  High: "sev-high sv-tone-strong sv-tone-ink",
  Medium: "sev-medium sv-tone-strong sv-tone-ink",
};
