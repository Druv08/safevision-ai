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
