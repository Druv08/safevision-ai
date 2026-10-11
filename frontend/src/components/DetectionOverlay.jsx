import { DETECTION_CLASSES } from "../theme";

/**
 * Bounding boxes over a media element. Place inside a `relative` wrapper that is
 * exactly the size of the rendered image/video; `width`/`height` are the source
 * pixel dimensions the boxes were computed on.
 */
function DetectionOverlay({ detections, width, height, hidden = [] }) {
  if (!width || !height) return null;
  return (
    <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
      {detections.map((d, i) => {
        if (!d.box || hidden.includes(d.class_id)) return null;
        const meta = DETECTION_CLASSES[d.class_id];
        const [x1, y1, x2, y2] = d.box;
        return (
          <div
            key={i}
            className={`${meta.tone} absolute rounded-[3px]`}
            style={{
              left: `${(x1 / width) * 100}%`,
              top: `${(y1 / height) * 100}%`,
              width: `${((x2 - x1) / width) * 100}%`,
              height: `${((y2 - y1) / height) * 100}%`,
              border: `2px solid var(--tone)`,
              boxShadow: "0 0 0 1px rgba(0,0,0,0.35)",
            }}
          >
            <span
              className={`absolute left-[-2px] px-1.5 py-0.5 rounded-[3px] text-[10px] font-semibold leading-none whitespace-nowrap ${
                // People are labelled above their box; PPE inside it, so nested labels don't collide.
                d.class_id === 0 ? "bottom-full mb-0.5" : "top-[-2px]"
              }`}
              style={{ background: "var(--tone)", color: "var(--canvas)" }}
            >
              {meta.label} {Math.round(d.confidence * 100)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default DetectionOverlay;
