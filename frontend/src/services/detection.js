import { LuCircleCheck, LuTriangleAlert, LuUserX } from "react-icons/lu";

export function formatBytes(n) {
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

/** Verdict for a /detect-image summary. Logged violations are per person, so use the summary. */
export function verdictFor(summary) {
  const violations = (summary?.no_helmet ?? 0) + (summary?.no_vest ?? 0);
  if (violations > 0) {
    return {
      tone: "danger",
      icon: LuTriangleAlert,
      title: `${violations} violation${violations > 1 ? "s" : ""} found`,
      text: "Missing PPE on detected workers. Each one is saved to the violations log with the frame as evidence.",
    };
  }
  if (!summary?.total_persons) {
    return { tone: "info", icon: LuUserX, title: "No workers detected", text: "No person was found, so no PPE rules were checked." };
  }
  return { tone: "ok", icon: LuCircleCheck, title: "All detected workers compliant", text: "No missing hard hat or vest was matched to a detected person." };
}
