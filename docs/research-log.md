# Research Log

This log is kept in a research-paper style so it can later be expanded into
an IEEE-style paper on SafeVision AI.

---

## 1. Dataset Used
- **Source:** Merged dataset built from two Roboflow YOLOv8 sources:
  1. `construction-safety-yolo` (17 classes, used for person/helmet/no_helmet/vest/no_vest subset)
  2. `vest-no-vest` v1 (2 classes: `vest`, `no vest`)
- **Final processed dataset:** `ai-model/datasets/processed/safevision-ppe-5class/`
- **Number of images:** 7,399 total (5,987 train / 740 valid / 672 test)
- **Train / Val / Test split:** 80.9% / 10.0% / 9.1%
  - Source 1: original train/valid/test kept
  - Source 2: original valid → valid; original train split 90/10 → train/test (seed=42)
- **Annotation format:** YOLO (txt per image, one class id per box)
- **Classes (remapped):** 0=person, 1=helmet, 2=no_helmet, 3=vest, 4=no_vest
- **Per-class instances (all splits):** person=69, helmet=436, no_helmet=108, vest=7,989, no_vest=7,717

## 2. Model Used
- **Architecture:** YOLOv8 (Ultralytics 8.4.60)
- **Variant:** yolov8n (nano, ~3M params)
- **Pretrained weights:** `yolov8n.pt`
- **Input image size:** 640

## 3. Training Setup
- **Run name:** `safevision_yolov8n_5class_v2`
- **Epochs:** 30
- **Batch size:** 8
- **Optimizer:** auto (SGD selected by ultralytics)
- **Hardware:** CPU (Intel Core Ultra 7 255HX), no CUDA
- **Total time:** ~2 h 30 min wall-clock training (1 pause + resume via `last.pt`)

## 4. Training Results

| Metric | Value |
|--------|-------|
| Precision | 0.590 |
| Recall    | 0.512 |
| mAP@0.5   | 0.481 |
| mAP@0.5:0.95 | 0.280 |
| FPS (inference, CPU) | ~30 (≈28 ms per 640×640 image) |

### Per-class metrics (best.pt, valid split)

| Class      | Instances | Precision | Recall | mAP50 | mAP50-95 |
|------------|----------:|----------:|-------:|------:|---------:|
| person     | 23  | 1.000 | 0.000 | 0.007 | 0.001 |
| helmet     | 115 | 0.396 | 0.539 | 0.450 | 0.215 |
| no_helmet  | 9   | 0.146 | 0.174 | 0.180 | 0.093 |
| vest       | 871 | 0.818 | 0.947 | **0.948** | **0.635** |
| no_vest    | 576 | 0.590 | 0.901 | **0.820** | **0.458** |

### Comparison vs v1 (17-class baseline)

| Class    | v1 mAP50 | v2 mAP50 | Δ |
|----------|---------:|---------:|--:|
| helmet   | 0.718 | 0.450 | -0.268 |
| no_helmet| 0.721 | 0.180 | -0.541 |
| vest     | 0.025 | **0.948** | **+0.923** |
| no_vest  | 0.050 | **0.820** | **+0.770** |
| person   | 0.030 | 0.007 | -0.023 |

## 5. Confusion Matrix
See `ai-model/outputs/training-runs/safevision_yolov8n_5class_v2/confusion_matrix.png` (kept locally, not committed — gitignored).

## 6. Testing Conditions
- Lighting: varied (indoor industrial, outdoor construction, low-light)
- Camera angle / distance: workers shot from ground level, distances ~2 m to ~30 m
- Indoor / outdoor: both
- Source images: still images from processed test split (672 images)
- Confidence threshold for reporting: 0.25

### Inference Sample (20 processed-test images, conf=0.25)

| Class      | Detections |
|------------|-----------:|
| person     | 0  |
| helmet     | 16 |
| no_helmet  | 0  |
| vest       | 16 |
| no_vest    | 18 |
| **Total**  | **50** |

19 of 20 images produced at least one detection. Highest single-image: 9 detections (image15: 5 vest + 3 helmet + 1 no_vest).

## 7. Failure Cases
- **Person class effectively non-functional**: only 69 training instances; model collapses to high precision (1.0) / zero recall.
- **no_helmet very weak**: only 108 total instances and 9 in valid — metric noisy and unreliable.
- **Helmet detection regressed from v1**: merged dataset is vest-heavy (7,989 vest vs 436 helmet labels), so the model allocated capacity toward vest classes.
- Occasional `NO-Hardhat` false positive on workers actually wearing helmets (observed in v1 inference at conf=0.27 — carries some risk into v2).

## 8. Screenshots / Evidence
- Annotated v2 inference outputs: `ai-model/outputs/predictions/day4_v2_predictions/` (local only — gitignored).
- Training curves: `ai-model/outputs/training-runs/safevision_yolov8n_5class_v2/results.png`.

## 9. Planned Improvements (Day 5+)
- **Re-balance dataset**: cap vest images at 2× helmet images, or use `class_weights` to compensate.
- **Add person data**: pull a person subset from COCO or another labeled set to push person mAP50 above 0.5.
- **Train v3 with longer schedule** (e.g. 60–80 epochs) once class balance is fixed.
- **Backend integration (Day 6+)**: serve `best.pt` via FastAPI `/predict` endpoint.

## 10. Day 5 — Live Video & Webcam Inference Observations

### Setup
- Script: `ai-model/inference/video_detection.py` (OpenCV + Ultralytics)
- Model: `safevision_yolov8n_5class_v2/weights/best.pt`
- Hardware: CPU (Intel Core Ultra 7 255HX), no CUDA
- Test 1: laptop webcam, indoor office lighting, plain desk background — `--conf 0.25`
- Test 2: 27 s screen recording (2560×1524), saved via `--save` at `--conf 0.4`

### Webcam test (conf 0.25)
| Metric              | Value |
|---------------------|------:|
| Frames processed    | 6,861 |
| Avg FPS (smoothed)  | 25.76 |
| `person` detections | 0     |
| `helmet` detections | 0     |
| `no_helmet` dets    | 0     |
| `vest` detections   | 321   |
| `no_vest` detections| 6,823 |

### Video file test (conf 0.4, saved annotated MP4)
| Metric              | Value |
|---------------------|------:|
| Input resolution    | 2560×1524 |
| Frames processed    | 812 |
| Avg FPS (smoothed)  | 13.50 |
| `person` detections | 0   |
| `helmet` detections | 0   |
| `no_helmet` dets    | 0   |
| `vest` detections   | 433 |
| `no_vest` detections| 268 |
| Output file size    | 67.7 MB |

### Confidence threshold observation
Raising `--conf` from 0.25 → 0.40 cut the `no_vest` per-frame rate from ~0.99 to ~0.33 (a ~3× reduction in spurious detections on background imagery) while `vest` precision visibly improved. **Recommended default for live deployment: `--conf 0.4`.** Lower thresholds (0.25) remain useful for offline review where recall matters more than precision.

### Suitability assessment of v2 for downstream use
- ✅ **Suitable** for video-based **vest / no_vest** detection in real time (CPU): high precision at 0.4, ~14–26 FPS depending on resolution.
- ❌ **Not yet suitable** for `person` detection (v2 effectively ignores the class — recall ≈ 0 in both image and video tests).
- ⚠️ **Marginally suitable** for `helmet` / `no_helmet` — fires on test images but did not fire on either video source in this session. Useful for static-image inference, unreliable for live video at this threshold.
- Conclusion: v2 + `--conf 0.4` is good enough to drive the MVP's **vest-violation** logic (Day 6+). `person`/`helmet`/`no_helmet` will need a v3 trained on a re-balanced dataset before they can be relied on.

## 11. References
- Ultralytics YOLOv8 docs — https://docs.ultralytics.com/
- Roboflow Universe: `construction-safety-yolo`, `vest-no-vest` v1
- Relevant PPE detection papers (to be cited in final paper)
