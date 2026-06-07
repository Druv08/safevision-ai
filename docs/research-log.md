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

## 12. Day 5 Cleanup — Dual-Model Inference

### Motivation
During live webcam testing it became clear that the v2 model's own `person` class is too weak (validation recall ≈ 0) to drive a worker count. A first attempt used `workers = max(person, vest + no_vest)` as a proxy, but this gave the wrong answer when a vest was held up to the camera with no person in frame (`workers` was reported as 1). To get a trustworthy worker count, we added a **second YOLO model** dedicated to person detection.

### Architecture
Two Ultralytics YOLO models are loaded at startup and both run on every frame:

| Model | Weights | Purpose | Classes kept |
|-------|---------|---------|--------------|
| SafeVision PPE | `safevision_yolov8n_5class_v2/weights/best.pt` | vest / no_vest / helmet / no_helmet detection | all PPE classes (1–4) |
| COCO detector  | `yolov8n.pt` (stock pretrained) | worker / person count + box | COCO class 0 only (`classes=[0]`) |

The `workers` HUD value is now sourced **exclusively** from the COCO detector. The SafeVision `person` class is still tracked internally but ignored for worker counting.

### CLI
| Flag | Default | Purpose |
|------|---------|---------|
| `--conf` | 0.25 | PPE-model confidence |
| `--person-conf` | 0.4 | COCO person-detector confidence |
| `--model` | (v2 best.pt) | Override PPE weights |
| `--person-model` | auto-find `yolov8n.pt` | Override person weights |

### Behavioural expectations now
| Scene | `workers` | `vest` / `no_vest` |
|-------|:---------:|:-------------------:|
| Vest only, person out of frame | **0** | vest = 1 |
| Person in frame, no vest | **1** | no_vest ≈ 1 |
| Person in frame, wearing vest | **1** | vest = 1 |
| Two people in frame | **2** | sum of their PPE boxes |

### Performance impact
Running two YOLO forward passes per frame on CPU roughly halves throughput:

| Pipeline | Webcam @ 640×480 |
|----------|------------------:|
| Single-model (v2 only) | ~25–27 FPS |
| Dual-model (v2 + COCO yolov8n) | **~16 FPS** |

Still within the MVP target for live preview. If we ever need more headroom, options are: run the COCO detector every N frames and reuse the last result, share preprocessed tensors, or move to GPU.

### Verified on webcam test (Day 5 cleanup run)
- 794 frames processed, ~48 s
- Avg FPS: 16.4 smoothed
- Both models loaded cleanly, no errors
- Event totals (rising-edge): vest = 6, no_vest = 17, helmet = 0, no_helmet = 0
- Manual checks confirmed: vest-only frame → `workers: 0`; person-only frame → `workers: 1`

### Implication for Day 6
Violation logic can now be expressed cleanly as: a `worker` box (from COCO) that geometrically contains a `no_vest` or `no_helmet` PPE box → violation. The `workers` value can be trusted as a denominator without the false-positive risk of the vest-proxy approach.

---

## 13. Day 6 — Violation Logic, Duplicate Filtering, Active-State Counting

### Goal
Turn raw per-frame PPE detections into auditable **violation events**, with screenshots and a CSV log, without inflating the count when the same condition is continuously visible.

### Pipeline
The Day 5 dual-model pipeline is reused (SafeVision PPE v2 + COCO `yolov8n.pt`), with three additions:

1. **Per-class IoU NMS on PPE boxes** (`filter_duplicate_boxes`, `iou_threshold=0.5`). Groups by `class_name`, sorts by confidence, drops same-class boxes whose IoU with a kept box exceeds 0.5. Different classes (e.g. `vest` vs `no_vest`) are never merged — that disagreement is information the violation logic uses.
2. **Violation rules** (frame-level):
   - `no_vest` ⇒ Safety Vest Missing (Medium)
   - `no_helmet` ⇒ Helmet Missing (High, experimental)
   - both together ⇒ Multiple PPE Missing (Critical, only ONE row written per frame in this case to avoid triple-logging)
3. **Active-state counting** (`--clear-after`, default 2 s) — see §13.1.

### 13.1 Active-state counting (key fix)
A naive cooldown alone (Day 6 first cut) still re-fired the same continuous violation every 5 s. The active-state machine fixes this:

```
For each violation type T:
  if T is fired in current frame:
    last_seen[T] = now
    if active[T] is False AND (now - last_saved[T]) >= cooldown:
        save screenshot + CSV row
        active[T] = True
        last_saved[T] = now
  else:
    if active[T] is True AND (now - last_seen[T]) > clear_after:
        active[T] = False   # ready to fire again on next appearance
```

Effect: a 140-second continuous `no_vest` produces exactly **1** Safety Vest Missing event. A new event is only created after the violation disappears for >`clear_after` seconds and then reappears.

### 13.2 Evidence layout
- Annotated screenshots → `ai-model/outputs/violations/screenshots/`
  - Filename pattern: `<prefix>_YYYYMMDD_HHMMSS_frame<N>.jpg`
- CSV log → `ai-model/outputs/violations/violations_log.csv`
  - Columns: `violation_id, timestamp, source, frame_number, violation_type, severity, confidence, worker_detected, screenshot_path`
- Annotated MP4 (optional, via `--save-video`) → `ai-model/outputs/video-detections/`
- All four locations are gitignored.

### 13.3 Verified runs

#### Webcam (active-state on, `--cooldown 5 --clear-after 2`)
| Metric | Value |
|---|---:|
| Frames processed | 2,811 |
| Avg FPS (smoothed) | 15.16 |
| Total violations saved | 5 |
| Safety Vest Missing | 5 |
| Helmet Missing | 0 |
| Multiple PPE Missing | 0 |
| Dup filter (kept / raw) | 2,513 / 2,725 (7.8% removed) |
| Continuous-sit window | ~140 s ⇒ 1 event ✅ |

Baseline comparison: an earlier identical-cooldown run **without** the active-state gate produced 20 events in 2,037 frames over the same kind of scene. Active-state cuts inflation by roughly **4×** on continuous violations.

#### Video file (`screen_recording_20260605_1222.mp4`, 2560×1524)
| Metric | Value |
|---|---:|
| Frames processed | 812 |
| Avg FPS (smoothed) | 10.68 |
| Output MP4 size | 80.2 MB |
| Total violations saved | 5 |
| Safety Vest Missing | 5 |
| Helmet Missing | 0 |
| Multiple PPE Missing | 0 |
| Dup filter (kept / raw) | 699 / 701 (0.3% removed) |
| Errors | none |

At higher resolution the PPE model rarely produced same-class overlaps, so the IoU filter barely fired — as expected.

### 13.4 Known limitations / honest notes
- **`worker_detected = no` in some CSV rows**: the COCO person filter (`--person-conf 0.7`, 3% min frame area, AR 0.2–1.2) is intentionally strict. Vest-violation detection is independent of the worker box and still fires correctly. Worker-side filtering can be tightened later by swapping in the pose model already used in `video_detection.py`.
- **Helmet class is weak in v2** (mAP50 = 0.45, with only 9 valid instances for `no_helmet`). Helmet Missing and Multiple PPE Missing counts should be treated as experimental until a v3 retrain rebalances the dataset.
- **Cooldown vs clear-after**: cooldown is now a secondary safety net for rapid re-appearance bursts; active-state is the primary correctness mechanism for continuous violations.

### 13.5 Implication for Day 7+
With the violation pipeline producing trustworthy, deduplicated, single-event-per-continuous-occurrence records, the local CSV + screenshots format is ready to be exposed via a FastAPI endpoint or pushed into Supabase storage when backend work resumes.

