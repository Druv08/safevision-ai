# SafeVision AI deployment guide

Planning notes for putting SafeVision on real site cameras. Everything here is a
starting point to validate on site, not a guarantee: detection quality depends
on the camera, the light, the distance and the workers' poses, and the models
were not trained on footage from every angle.

## What one camera can do

- A camera only sees its own field of view. Every safety zone that must be
  monitored needs a camera that sees it; overlapping views help with occlusion.
- The AI judges each worker it can see: helmet worn / missing and vest worn /
  missing. A worker hidden behind machinery, or too small in the picture, is not
  judged (no false violation, but no protection either).
- Wider coverage means fewer pixels per worker. Distant workers become
  unreliable first; check the furthest working position in the live view.

## Placement (hypotheses to test on site)

| Topic | Starting recommendation | Why / caveat |
|---|---|---|
| Height and angle | High corner, about 30-45 degrees downward | Shows head and torso. Straight overhead views hide the vest and face; helmet detection from steep angles is not validated with our data |
| Resolution | 1080p or higher | A planning value, not a measured detection range |
| Worker size in frame | Head and torso clearly visible; test the smallest worker you need | The pose model needs visible shoulders/hips to accept a worker; the COCO person fallback covers some partial views |
| Lighting | Even light, no strong backlight at the camera | Hard-hat colour assist uses colour; glare and dusk reduce it |
| Occlusion | Cover each zone from two directions where workers cluster | One worker hidden by another is not judged |

## Network and compute

- Cameras: RTSP (`rtsp://` or `rtsps://`), added on the Cameras page. Credentials
  are encrypted at rest (`CAMERA_SECRET_KEY`) and never shown in status or logs.
- Bandwidth: plan a few Mbit/s per 1080p H.264 stream on the local network;
  keep cameras and the SafeVision computer on the same LAN where possible.
- Each camera is sampled at `STREAM_SAMPLE_FPS` (default 5) analysed frames per
  second. All cameras share one model instance on one lock, so total
  throughput is divided between cameras.
- Measured on the development laptop CPU (this repository, unified engine,
  1280x762 frames): about 70-95 ms per frame for one stream, and two simulated
  streams each held ~4.6-4.8 analysed fps at a 5 fps target. More cameras or
  higher sampling rates need their own benchmark; a GPU or a faster CPU is the
  usual answer, not a guaranteed figure.

## Configuration checklist

1. Weights present locally (not in Git): v5d `best.pt`, `yolov8n-pose.pt`,
   `yolov8n.pt` (paths in the README).
2. `backend/.env`: Supabase keys (production) or `DB_DISABLED=true` +
   `AUTH_DISABLED=true` (local demo only), model paths, `CAMERA_SECRET_KEY`,
   `EVIDENCE_SECRET_KEY`, `SITE_TIMEZONE`, `SHIFTS`.
3. Add each camera (name, RTSP URL, sample fps), draw its zones, set alert
   recipients.
4. Walk the site in PPE and without: confirm every zone produces correct
   per-worker results before relying on alerts.

## Cost planning (indicative ranges, not quotations)

Figures are rough Indian-market planning ranges for budgeting a pilot; get
vendor quotes before committing.

| Item | Planning range | Notes |
|---|---|---|
| Reuse existing IP/CCTV cameras | 0 (if RTSP is available) | Many NVR systems expose RTSP; check resolution and angle |
| New 1080p-4MP IP camera (outdoor, PoE) | approx. INR 3,000-12,000 each | Higher for long-range / low-light models |
| Local computer / edge box | approx. INR 50,000-1,50,000 | CPU-only for a pilot; GPU for several cameras (benchmark first) |
| Installation, PoE switch, cabling, storage | approx. INR 2,000-8,000 per camera + INR 10,000-40,000 one-off | Site dependent |
| Optional subscription (proposal) | e.g. INR 1,000-3,000 per camera per month | A pricing idea for hosting, updates and support, not a market rate |

## Known limitations

- No guarantee for workers far from the camera, in heavy occlusion, at night
  without IR, or seen from directly above.
- Held helmets and hard hats held at the chest are rejected by explicit rules;
  unusual PPE (other colours, other vest designs) was not validated.
- Throughput for many simultaneous cameras on CPU has not been benchmarked.
