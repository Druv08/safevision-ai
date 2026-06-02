# Project Notes

## Final MVP Scope

SafeVision AI MVP will:

1. Take input from a video file or webcam.
2. Run YOLO-based PPE detection on each frame.
3. Detect violations (worker without helmet or without safety vest).
4. Save a screenshot of each violation.
5. Store violation details (timestamp, type, image URL) in Supabase.
6. Show violations on a Next.js dashboard with a basic report view.

## Classes Planned

- `person`
- `helmet`
- `vest`
- `no_helmet`
- `no_vest`

## Advanced Features (Later, Not in MVP)

- Restricted / no-entry zone detection
- Fall detection
- WhatsApp / email alerts on violations
- PDF safety report generation
- Multi-camera support
- Role-based authentication for dashboard
- Real-time live streaming via WebRTC
