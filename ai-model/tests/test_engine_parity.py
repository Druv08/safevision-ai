"""
Parity: the shared engine must make the same per-frame decisions as the
standalone live camera (video_detection.main()).

The original main() is run unmodified on a short clip with its window calls
stubbed and draw_hud() patched to record what the HUD shows each frame; the
engine is then run on the same frames. Needs the real weights and a clip, which
are not in Git:

    SAFEVISION_PARITY_VIDEO=path/to/clip.mp4
    PPE_MODEL_PATH=.../safevision_yolov8n_5class_v5d_50epochs/weights/best.pt
    PERSON_MODEL_PATH=.../yolov8n-pose.pt
    (COCO person fallback: yolov8n.pt in the repo root, as for the camera)

Without them the test is skipped with that reason (it is not a pass).
"""

import os
import sys
from pathlib import Path

import pytest

INFER = Path(__file__).resolve().parents[1] / "inference"
sys.path.insert(0, str(INFER))

VIDEO = os.getenv("SAFEVISION_PARITY_VIDEO", "")
PPE = os.getenv("PPE_MODEL_PATH", "")
POSE = os.getenv("PERSON_MODEL_PATH", "")
MAX_FRAMES = int(os.getenv("SAFEVISION_PARITY_FRAMES", "120"))

pytestmark = pytest.mark.skipif(
    not (VIDEO and Path(VIDEO).is_file() and Path(PPE).is_file() and Path(POSE).is_file()),
    reason="parity needs SAFEVISION_PARITY_VIDEO, PPE_MODEL_PATH and PERSON_MODEL_PATH (local assets)",
)


def _clip(tmp_path):
    """First MAX_FRAMES frames of the video, so both sides read identical frames."""
    import cv2

    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    out, frames = None, []
    path = tmp_path / "clip.avi"
    while len(frames) < MAX_FRAMES:
        ok, f = cap.read()
        if not ok:
            break
        if out is None:
            out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (f.shape[1], f.shape[0]))
        out.write(f)
        frames.append(f)
    cap.release()
    out.release()
    return path


def test_engine_matches_live_camera_frame_by_frame(tmp_path, monkeypatch):
    import cv2

    import safevision_engine as se
    import video_detection as vd

    clip = _clip(tmp_path)

    # 1) Original live camera, unmodified, recording its HUD every frame.
    hud = []
    monkeypatch.setattr(vd, "draw_hud", lambda frame, fps, display, workers_n: hud.append(
        {"workers": workers_n, **{k: display[k] for k in ("helmet", "no_helmet", "vest", "no_vest")}}))
    for name in ("namedWindow", "imshow", "destroyAllWindows"):
        monkeypatch.setattr(vd.cv2, name, lambda *a, **k: None)
    monkeypatch.setattr(vd.cv2, "waitKey", lambda *a: -1)
    monkeypatch.setattr(vd.cv2, "getWindowProperty", lambda *a: 1.0)
    monkeypatch.setattr(sys, "argv", ["video_detection.py", "--source", str(clip), "--model", PPE,
                                      "--pose-model", POSE, *se.DEMO_ARGV])
    assert vd.main() == 0
    assert hud, "live camera processed no frames"

    # 2) Engine on the same frames, one stream state.
    engine = se.SafeVisionEngine(PPE, POSE, vd.DEFAULT_PERSON_MODEL).load_models()
    state = engine.new_state()
    cap = cv2.VideoCapture(str(clip))
    got = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        r = engine.process_frame(frame, state=state)
        got.append({k: r.hud[k] for k in ("workers", "helmet", "no_helmet", "vest", "no_vest")})
        c = r.counts
        assert c["helmet"] + c["no_helmet"] == c["workers"] == c["vest"] + c["no_vest"]
    cap.release()

    assert len(got) == len(hud)
    mismatches = [(i, a, b) for i, (a, b) in enumerate(zip(hud, got)) if a != b]
    assert not mismatches, f"{len(mismatches)}/{len(hud)} frames differ, first: {mismatches[:3]}"
