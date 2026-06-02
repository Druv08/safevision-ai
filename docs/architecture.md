# SafeVision AI - Architecture

High-level data flow for the MVP:

```
Video / Webcam Input
        │
        ▼
YOLO PPE Detection  (person, helmet, vest, no_helmet, no_vest)
        │
        ▼
Violation Logic     (e.g. person detected without helmet/vest)
        │
        ▼
Screenshot Capture  (save frame of the violation)
        │
        ▼
FastAPI Backend     (receives + processes detections)
        │
        ▼
Supabase Database + Storage  (violation records + screenshot URLs)
        │
        ▼
Next.js Dashboard   (live list of violations, filters)
        │
        ▼
Safety Report       (summary view / exportable report)
```

## Components

- **YOLO PPE Detection** — Ultralytics YOLOv8, custom-trained on PPE classes.
- **Violation Logic** — Python rules that decide when a frame is a violation.
- **FastAPI Backend** — REST API, handles uploads and forwards data to Supabase.
- **Supabase** — Postgres DB for violation rows + Storage bucket for screenshots.
- **Next.js Dashboard** — UI for viewing violations and generating reports.
