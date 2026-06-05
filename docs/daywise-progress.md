# Day-wise Progress

## Day 1 — Project Setup

### Completed
- [x] Created GitHub repository `safevision-ai` and cloned locally
- [x] Created base folder structure (`ai-model/`, `backend/`, `frontend/`, `docs/`)
- [x] Added `backend/requirements.txt` with core dependencies
- [x] Created FastAPI starter (`backend/main.py`) with `/` and `/health` routes
- [x] Added `backend/.env.example` for Supabase config
- [x] Added YOLO sanity test script (`ai-model/inference/test_yolo.py`)
- [x] Added OpenCV webcam test script (`ai-model/inference/test_opencv.py`)
- [x] Wrote initial docs: `architecture.md`, `project-notes.md`, `research-log.md`
- [x] Updated root `README.md` with setup + run instructions

### Issues Faced
- _None yet — fill in here as we run the test scripts and backend._

### Next Day Plan (Day 2)
- Find a suitable PPE detection dataset (Roboflow / Kaggle / open sources)
- Understand the YOLO dataset format (`images/`, `labels/`, `data.yaml`)
- Finalize the class list: `person`, `helmet`, `vest`, `no_helmet`, `no_vest`
- Prepare `data.yaml` for training
- Decide on train/val/test split

---

## Day 4 — Train and Test 5-Class SafeVision Model

### Completed
- [x] Acquired second PPE dataset (Roboflow `vest-no-vest v1`, 7,205 labels)
- [x] Built merged 5-class processed dataset at `ai-model/datasets/processed/safevision-ppe-5class/`
  - 5,987 train / 740 valid / 672 test images
  - Class instance counts: person=69, helmet=436, no_helmet=108, vest=7,989, no_vest=7,717
- [x] Wrote dataset builder (`ai-model/training/build_safevision_5class_dataset.py`) with class remap + 90/10 train→test split for source 2 (seed=42)
- [x] Wrote 5-class training script (`ai-model/training/train_safevision_5class.py`) with `--smoke`, `--fast`, `--resume` modes
- [x] Verified pipeline with smoke run (1 epoch → vest mAP50 already 0.80)
- [x] Completed full 30-epoch training on CPU (`safevision_yolov8n_5class_v2`)
- [x] Wrote v2 inference test (`ai-model/inference/test_safevision_5class_model.py`)
- [x] Ran inference on 20 processed-test images at conf=0.25

### v2 Final Metrics (best.pt, valid split)
| Metric    | Value |
|-----------|-------|
| Precision | 0.590 |
| Recall    | 0.512 |
| mAP50     | 0.481 |
| mAP50-95  | 0.280 |

Per-class mAP50: person 0.007 · helmet 0.450 · no_helmet 0.180 · **vest 0.948** · **no_vest 0.820**

### v2 Inference (20 test images, conf=0.25)
person 0 · helmet 16 · no_helmet 0 · vest 16 · no_vest 18 (total 50 detections)

### Issues Faced
- First training run had no `test/` split in `ppe-vest-yolo` — handled by 90/10 split from `train/` (seed=42)
- Same-terminal polling killed an earlier run via Ctrl+C; added `--resume` flag to recover from `last.pt` checkpoint
- Helmet mAP regressed vs v1 (0.72 → 0.45) because merged set is now vest-heavy; trade-off accepted for MVP

### Next Day Plan (Day 5)
- Integrate `safevision_yolov8n_5class_v2/weights/best.pt` into FastAPI backend
- Add `/predict` endpoint accepting an uploaded image
- Return JSON with detections (class, conf, bbox) + optional annotated image
