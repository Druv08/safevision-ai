# SafeVision AI

AI-powered PPE (Personal Protective Equipment) safety monitoring system for
factories, warehouses, and construction sites.

## Problem Statement

In industrial workplaces, workers are required to wear safety gear like
helmets and high-visibility vests. Manual monitoring through CCTV is slow,
error-prone, and cannot scale. Missed violations lead to serious injuries.

## Solution

SafeVision AI uses a YOLO-based computer vision model to automatically
detect workers in video/webcam streams and flag PPE violations (missing
helmet or missing vest). Violations are screenshotted, stored, and shown
on a dashboard so safety officers can review them in one place.

## MVP Features

- Detect persons, helmets, and safety vests from video/webcam input
- Flag violations: `no_helmet`, `no_vest`
- Capture and save a screenshot of each violation
- Store violation metadata (time, type, image) in a database
- Dashboard to view and filter violations
- Basic safety report view

## Tech Stack

- **AI / CV:** Python, Ultralytics YOLOv8, OpenCV, NumPy, Pillow
- **Backend:** FastAPI, Uvicorn
- **Database & Storage:** Supabase (Postgres + Storage)
- **Frontend:** Next.js (to be added)
- **Tooling:** Git/GitHub, Python venv

## Folder Structure

```
safevision-ai/
├── ai-model/
│   ├── datasets/        # Datasets (added later)
│   ├── training/        # Training scripts + data.yaml
│   ├── inference/       # Test + inference scripts
│   ├── outputs/         # Predictions, screenshots, weights
│   └── README.md
├── backend/
│   ├── main.py          # FastAPI entry point
│   ├── routes/          # API route modules
│   ├── services/        # Business logic (detection, storage)
│   ├── uploads/         # Temp upload folder
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/            # Next.js app (added later)
├── docs/
│   ├── architecture.md
│   ├── daywise-progress.md
│   ├── project-notes.md
│   └── research-log.md
└── README.md
```

## Day 1 Setup (Windows)

### 1. Create and activate a Python virtual environment

```powershell
python -m venv venv
venv\Scripts\activate
```

### 2. Upgrade pip and install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 3. Test YOLO

```powershell
python ai-model/inference/test_yolo.py
```

This downloads `yolov8n.pt` on first run and saves an annotated image
under `runs/detect/predict/`.

### 4. Test OpenCV / webcam

```powershell
python ai-model/inference/test_opencv.py
```

Press `q` in the video window to quit.

### 5. Run the FastAPI backend

```powershell
cd backend
uvicorn main:app --reload
```

Then open in your browser:

- http://127.0.0.1:8000        — root endpoint
- http://127.0.0.1:8000/docs   — interactive API docs (Swagger UI)

### 6. Frontend

The frontend will be set up with **Next.js** in a later step:

```powershell
npx create-next-app@latest frontend
```

## Status

Day 1: Project scaffold + dependencies + smoke tests for YOLO, OpenCV and
FastAPI. No model training, no dataset, no auth yet.
