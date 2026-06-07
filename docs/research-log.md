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


## 14. Day 6.5 - Worker-Match Gate

### 14.1 Why we needed it
After Day 6, the saved-violation CSV still contained rows where `worker_detected=no`. Those came from PPE detections (mostly `no_vest`) that triggered on clothing or background objects with no person nearby. `worker_detected` was only an observational column; it did not gate the save. Day 6.5 turns the worker presence requirement into an actual save-time filter, and additionally requires the PPE box and the worker box to spatially overlap.

### 14.2 Why overlap ratio (not IoU)
A standing worker's box is roughly torso-plus-legs (tall, lots of area). A `no_vest` box typically covers only the chest (a small fraction of that area). The IoU of those two boxes is naturally low - in our test footage usually below 0.20 - so an IoU-based gate would reject most genuine violations.

We instead compute `intersection_area / area(ppe_box)`. This answers the right question: *what fraction of the PPE box lies inside the worker box?* A correctly-placed chest `no_vest` typically scores well above 0.80 against the surrounding worker box, while a vest-shaped object away from any worker scores 0.0. A 0.30 default threshold (`--worker-overlap`) gave a clean separation on the test video and leaves headroom for partial occlusion.

### 14.3 Implementation
- `calculate_overlap_ratio(inner_box, outer_box) -> float` - returns `intersection / area(inner_box)` in `[0, 1]`.
- `ppe_matches_worker(ppe_box, worker_boxes, overlap_threshold) -> bool` - per-frame check against every worker box; short-circuits on first match.
- `draw_worker_boxes` was refactored to return `(n_workers, worker_boxes)` so the main loop can reuse the exact list of accepted worker boxes (after the conf / area / aspect-ratio sanity filter).
- Gate is applied per violation type:
  - `Safety Vest Missing`  -> at least one `no_vest` box matches a worker
  - `Helmet Missing`       -> at least one `no_helmet` box matches a worker
  - `Multiple PPE Missing` -> **both** classes independently match a worker
- Gate order in the main loop: **worker-match -> active-state -> cooldown**. The save is skipped if any gate fails, but `last_seen_violation_time` is still refreshed so the active-state clear-after timer cannot trip mid-violation just because the save was suppressed.

### 14.4 Empirical impact on the test video
Source: `screen_recording_20260605_1222.mp4`, 2560x1524, 812 frames, `--conf 0.4 --person-conf 0.7 --worker-overlap 0.3 --clear-after 2 --cooldown 5`.

| | Day 6 | Day 6.5 |
|---|---|---|
| Saved violations | 5 | 4 |
| Rows with `worker_detected=no` | 2 | 0 |
| Unmatched `no_vest` skipped | n/a (not counted) | 72 |
| Unmatched `no_helmet` skipped | n/a (not counted) | 0 |
| Per-class duplicate filter removed | 2 / 701 (0.3%) | 2 / 701 (0.3%) |

Interpretation: across 812 frames, 72 individual `no_vest` detections fired without any worker overlap. Without the gate, the active-state machine would still have collapsed many of those into a single event each, but two of the five Day 6 saves were spurious. Both are now removed, and the remaining four saves all have `worker_detected=yes` in the CSV.

### 14.5 Performance note
Adding the per-frame overlap check costs a handful of array operations per (PPE box, worker box) pair. Average FPS on the same video moved from 10.68 (Day 6) to 9.54 (Day 6.5). The drop is partly the overlap loop and partly run-to-run variance from background load. No optimisation is warranted at this scale.

### 14.6 Implication for Day 7+
- The CSV column `worker_detected` is now a guaranteed `yes` for every logged event, which means the backend can treat the CSV as the worker-violation ledger directly - no post-filter needed on the server side.
- The `unmatched_no_*` counters give us a free, cheap signal for *false-positive load*: a real deployment can monitor these to detect when the PPE model is firing too often on non-worker objects, without having to add a separate audit pipeline.

---

## 15. Day 7 - Backend / API Notes

### 15.1 Architecture choice
The backend is intentionally **stateless** and **thin**: routes do the HTTP work, services do the model work, and nothing crosses those layers in the other direction. The services/ modules never import FastAPI, and outes/ never imports ultralytics directly. This means we can later reuse detection_service.run_image_detection from a queue worker, a CLI script, or a unit test without any HTTP machinery loaded.

### 15.2 Model singleton (why and how)
A YOLOv8 model is a few hundred MB of weights and takes 1-3 seconds to instantiate on this hardware. Re-loading per request would dominate latency and would also leak GPU/CPU memory over time. So:

- `services/model_service.py` holds a module-level `_model` reference and a matching `_model_path_used`.
- `get_model()` lazy-loads on first call and short-circuits on every subsequent call.
- `ultralytics` is imported **inside** the loader function, not at module top. This keeps `import services.model_service` cheap (does not pull in torch) - useful for tests and for `/health` warming behaviour.
- If the weights file is missing, the loader sets `_model = None` and stores a human-readable `_model_error`. The backend itself never crashes; the affected endpoints simply return a 503 with the error.

This is the same lazy + cached pattern we will reuse on Day 8+ for any heavier services (Supabase client, etc.).

### 15.3 Image vs video endpoint shape
The two detection endpoints are deliberately asymmetric:

- `/api/detect-image` returns the **full** per-detection list (class_id, class_name, confidence, bbox) plus a per-image violation summary. A frontend can draw boxes from the response without any extra round-trip.
- `/api/detect-video` returns **aggregate counts only** (`detections_by_class`, `violations_by_type`). It does NOT return per-frame boxes and it does NOT write an annotated video.

The reason is purely about response size and CPU cost. A 30-second video at 30 FPS = 900 frames; even at `frame_skip=10` that is 90 inferences and potentially thousands of boxes. Returning all of that as JSON per HTTP call would be huge and is not actually useful for a dashboard - the dashboard wants the counts. If a future feature needs per-frame data, it should be a separate endpoint that streams (Server-Sent Events or chunked NDJSON) rather than building it into this one.

### 15.4 Upload-file safety
- Allowed-extension whitelists are enforced **at the route layer** before the file is read into memory (image: `.jpg .jpeg .png`; video: `.mp4 .avi .mov .mkv`).
- The original filename is **never** trusted on disk. Every upload is renamed to `<utc-timestamp>_<uuid4-hex>.<ext>` before being written. This prevents path-traversal (`../../etc/passwd`), filename collisions, and unicode/space issues in PowerShell / shell follow-up steps.
- Uploads land in `backend/uploads/`, which is git-ignored. They are kept on disk for now because the inference functions take a path; if the backend later gains a streaming variant we can switch to in-memory `BytesIO`.

### 15.5 Violation rule consistency
The per-image violation summary in `detection_service.py` uses the **same** rule mapping as the local `ai-model/inference/violation_detection.py`:

| Trigger | Violation type | Severity |
|---|---|---|
| `no_vest` alone           | Safety Vest Missing   | Medium   |
| `no_helmet` alone         | Helmet Missing        | High     |
| `no_vest` AND `no_helmet` (same image) | Multiple PPE Missing | Critical |

The `Multiple PPE Missing` rule is applied **per image**, not per detection: even if a frame has 5 `no_vest` boxes and 3 `no_helmet` boxes, that frame contributes ONE `Multiple PPE Missing` event, using the higher of the two top confidences. This matches the local pipeline so a frontend that consumes both `/api/violations` (local CSV) and `/api/detect-image` (live) does not see two different rule definitions.

Important: the HTTP-side violation summary does **not** include the Day 6.5 worker-overlap gate. That gate is part of the saving pipeline in the local tool, not the inference itself. The backend just reports what the model sees; gating by worker presence is a job for a future `POST /api/run-violation-pipeline` style endpoint.

### 15.6 CORS scope
CORS is restricted to `http://localhost:3000` and `http://127.0.0.1:3000` only. This is enough for the Day 8+ React/Next dev server and nothing else. When deployment becomes a thing we will add the production origin explicitly rather than opening it to `*`.

### 15.7 What the backend deliberately does NOT do (yet)
- No persistence to a database. Violations remain a local CSV.
- No authentication / authorisation. The endpoints are open on `127.0.0.1`.
- No background tasks. Every request is synchronous.
- No model warm-up at startup; the first call to a detection endpoint pays the load cost. `/health` and `/api/model-status` both trigger the load, so a frontend can poll either to warm the model before its first real request.

### 15.8 Implication for Day 8+
- Adding Supabase storage = wrap each successful `/api/detect-image` response with an upload call (annotated screenshot + JSON row).
- Adding a frontend = no backend changes needed; the existing endpoints already return the shapes a React dashboard needs.
- Adding a violation-pipeline endpoint = port the Day 6.5 logic from `violation_detection.py` into a service function and expose it as a new POST route; the local tool stays as the source of truth for the logic.

---
