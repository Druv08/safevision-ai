"""
Export YOLO weights to ONNX for a small edge computer (CPU, onnxruntime).

    python ai-model/training/export_onnx.py                      # the three weights the backend uses
    python ai-model/training/export_onnx.py path/to/best.pt ...  # specific files
    python ai-model/training/export_onnx.py --imgsz 480 --half   # smaller / faster (check accuracy!)

Each <name>.pt becomes <name>.onnx next to it (class names and task are stored
in the ONNX metadata, so the pipeline still finds helmet / vest / person by
name). Then point the backend or the CLIs at the .onnx files:

    PPE_MODEL_PATH=.../best.onnx  HELMET_MODEL_PATH=.../best.onnx  PERSON_MODEL_PATH=.../yolov8n-pose.onnx

or  python ai-model/inference/video_detection.py --model x.onnx --helmet-model y.onnx --person-model z.onnx

ONNX models run at a fixed input size (--imgsz, default 640); frames are
letterboxed to it. After exporting, every model is loaded back and run on a
blank frame, and the .pt and .onnx outputs are compared on one test image if
--check-image is given. Re-run evaluate.py with the .onnx weights before
deploying: accuracy should match the .pt within rounding.

Needs:  pip install -r backend/requirements-onnx.txt   (onnxruntime to run, onnx + onnxslim to export)
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import weights  # noqa: E402


def export(pt: Path, imgsz: int, half: bool, opset: int | None) -> Path:
    from ultralytics import YOLO

    model = YOLO(str(pt))
    out = model.export(format="onnx", imgsz=imgsz, half=half, dynamic=False, simplify=True,
                       opset=opset, device="cpu")
    return Path(out)


def check(pt: Path, onnx: Path, image: Path | None, imgsz: int) -> None:
    import cv2
    import numpy as np
    from ultralytics import YOLO

    from services.pipeline import load_yolo

    m = load_yolo(onnx)  # the same loader the backend uses: task from the ONNX metadata
    expected = YOLO(str(pt)).task
    if m.task != expected:
        raise SystemExit(f"[ERROR] {onnx.name} loads as task {m.task!r}, expected {expected!r}")
    frame = cv2.imread(str(image)) if image else np.zeros((480, 640, 3), np.uint8)
    r = m.predict(frame, imgsz=imgsz, verbose=False)[0]
    print(f"  loaded {onnx.name}: task={m.task}, {len(m.names)} classes, {len(r.boxes)} boxes on the check frame")
    if image:
        ref = YOLO(str(pt)).predict(frame, imgsz=imgsz, verbose=False)[0]
        print(f"  .pt found {len(ref.boxes)} boxes, .onnx found {len(r.boxes)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("weights", nargs="*", type=Path,
                    help="default: PPE, helmet and person weights from backend/weights.py")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--half", action="store_true", help="FP16 (smaller file; needs a runtime that supports it)")
    ap.add_argument("--opset", type=int, default=None)
    ap.add_argument("--check-image", type=Path, help="compare .pt and .onnx detections on this image")
    args = ap.parse_args(argv)

    paths = args.weights or list(dict.fromkeys(
        weights.resolve(k) for k in ("PPE_MODEL_PATH", "HELMET_MODEL_PATH", "PERSON_MODEL_PATH")))
    for pt in paths:
        if pt.suffix != ".pt" or not pt.is_file():
            print(f"[ERROR] not a .pt file: {pt}")
            return 1
    for pt in paths:
        print(f"Exporting {pt}")
        try:
            onnx = export(pt, args.imgsz, args.half, args.opset)
            check(pt, onnx, args.check_image, args.imgsz)
        except ModuleNotFoundError as e:
            print(f"[ERROR] {e}. Install: pip install -r backend/requirements-onnx.txt")
            return 1
        print(f"  -> {onnx} ({onnx.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
