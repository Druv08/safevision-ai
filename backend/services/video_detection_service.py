import cv2

from config import settings
from services.detection_service import analyze_frame
from services.model_service import model_version
from services.violations_service import save_violation

# Used when the container reports no usable frame rate.
FALLBACK_FPS = 30.0


class VideoDecodeError(ValueError):
    pass


def detect_video(video_path, source="video"):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VideoDecodeError("Could not open the video file.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not 0 < fps < 240:  # webm from MediaRecorder often reports 0 or 1000
        fps = FALLBACK_FPS

    version = model_version()
    counts = {"no_helmet": 0, "no_vest": 0}
    # Cooldown is measured in video time, so results don't depend on how fast
    # the server processes frames.
    last_saved_at = {"no_helmet": float("-inf"), "no_vest": float("-inf")}
    frame_number = 0
    events = []  # one entry per saved violation, with its position in the video

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break
            frame_number += 1

            pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            video_time = pos_ms / 1000.0 if pos_ms > 0 else (frame_number - 1) / fps

            _, _, violations = analyze_frame(frame)
            best = {}
            for vtype, conf in violations:
                best[vtype] = max(conf, best.get(vtype, 0.0))

            for vtype, conf in best.items():
                if video_time - last_saved_at[vtype] >= settings.video_cooldown_seconds:
                    save_violation(frame, vtype, conf, source, version)
                    counts[vtype] += 1
                    events.append({"type": vtype, "time": round(video_time, 2), "confidence": round(conf, 3)})
                    last_saved_at[vtype] = video_time
    finally:
        cap.release()

    if frame_number == 0:
        raise VideoDecodeError("No frames could be decoded from the video.")

    return {
        "status": "processed",
        "message": "Video analyzed successfully",
        "frames_processed": frame_number,
        "total_violations": counts["no_helmet"] + counts["no_vest"],
        "helmet_violations": counts["no_helmet"],
        "vest_violations": counts["no_vest"],
        "duration_seconds": round(frame_number / fps, 2),
        "events": events,
    }
