# Evaluation protocol

How SafeVision models and the violation pipeline are evaluated. The aim is
numbers that predict behaviour on a camera the model has never seen, and that
measure what a site manager experiences, namely alerts, not boxes.

Tools: `ai-model/training/split_by_camera.py`, `ai-model/training/evaluate.py`,
and `ai-model/training/train_safevision_v5.py` (writes `metrics.json`).

## 1. Held-out split by camera or source

**Rule:** frames from one camera, recording session or source video, and all
augmented copies of one source image, go to exactly one of train / val / test.

Why: consecutive frames are near-duplicates. With a random image-level split,
the test set contains frames that the model has effectively seen during
training. The original Roboflow split of the construction-safety dataset has
this problem: 20 of its 91 valid/test images come from a video
(`construction-1-_mp4` … `construction-5-_mp4`, `IMG_1493_mp4`, …) that also
has frames in another split. All earlier mAP figures in `research-log.md` were
measured on splits like this, so they are optimistic.

Procedure:

1. Run the split on the **raw** datasets, not on `datasets/processed/*`. The
   processed file names (`ves_tra_000001`) no longer say which camera or
   video a frame came from. The tool refuses to split when it finds fewer than
   10 groups.
2. Check the "largest groups" printout. The default key is the file stem with
   the Roboflow suffix and the trailing frame number removed. If that is wrong
   for a dataset, pass `--group-regex` or a `--group-map` CSV (`image,group`).
   Webcam captures should be grouped by session, e.g. `webcam_s03`.
3. Use test 20 %, val 10 %, seed 42 (the defaults). Keep `split_manifest.json`
   with the results; it records which group went where.
4. Never tune thresholds, pick epochs or choose between runs on **test**. Use
   **val** for that. Test is reported once per candidate model.

```bash
python ai-model/training/split_by_camera.py <raw dataset> <out> --seed 42
```

When combining datasets (as v5 does), split each source first and merge the
splits, so that no camera crosses splits through any source.

## 2. Detector metrics

```bash
python ai-model/training/evaluate.py detector --weights <best.pt> --data <out>/data.yaml --split test --out test.json
```

The report gives per-class precision, recall, mAP50 and mAP50-95 (Ultralytics
`val`, IoU 0.5 and 0.5:0.95, imgsz 640) plus the instance count of each class.
Points to keep in mind:

- **Look at the instance counts.** A class with under ~50 test instances has
  very wide error bars. For example, the construction-safety test split has 7
  `NO-Hardhat` boxes.
- **Use the deployed weights.** The classes that matter are those the pipeline
  actually uses: `helmet`/`no_helmet` from the helmet model, `vest`/`no_vest`
  from the PPE model, and `person` from the person model.
- **Report them together.** A model can have high mAP and still trigger false
  alarms, which is what section 3 measures.

Every training run of `train_safevision_v5.py` uses seed 42 with deterministic
mode (`--seed` to change) and writes `<run>/metrics.json`: val and test metrics
in this format, plus dataset, base weights, epochs, image size, batch, device,
Ultralytics version and git commit. Compare runs only when their `data` is the
same split.

## 3. Event metrics on labelled video

This tests the whole pipeline: detection, association to a person, tracking,
and the time window. It runs exactly the same code as the backend.

### Labelling

For each test video, write `<video>_events.csv` with one row per **episode**:
one person, one item, continuously missing.

```
type,start_s,end_s
no_helmet,12.0,31.5
no_vest,40.2,44.0
```

- `start_s` is the first moment the item is visibly missing and the person is
  visible. `end_s` is the last such moment.
- If a person leaves the view for more than 1 s and returns still without the
  item, start a new episode. This matches `VIOLATION_CLEAR_SECONDS`.
- Two people missing the same item at the same time are two rows.
- Label every episode, including short ones. Episodes shorter than the window
  are reported separately (see below).
- Use videos from cameras that are **not** in the training split, and record
  which test videos were used.

### Matching

Each alert is the moment an episode opened (the time the 2 s window was
satisfied). An alert is matched to a labelled episode of the same type if its
time falls in `[start_s - 1 s, end_s + 1 s]` (`--tolerance`):

- the first alert on an episode is a **true positive**;
- further alerts on an already-alerted episode are **duplicates**. These are
  usually caused by a tracker ID switch or an occlusion longer than the clear
  time;
- an alert matching no episode is a **false positive**;
- an episode with no alert is a **miss**.

Simultaneous episodes of the same type are matched earliest-start first. The
matching uses time only, so with several people violating at once it cannot
tell whose alert is whose. For crowded clips, also check the `alerts` list
(which includes `track_id`) by eye.

### Reported numbers

```bash
python ai-model/training/evaluate.py video --video site.mp4 --labels site_events.csv --out site.json
```

| Metric | Definition |
|---|---|
| precision | true positives / alerts. Duplicates count against it, because each duplicate is a real extra notification. |
| precision_ignoring_duplicates | (true positives + duplicates) / alerts |
| recall | detected episodes / all labelled episodes |
| recall_alertable | the same, over episodes at least as long as the window |
| duplicates_per_detected_episode | duplicates / true positives |
| time_to_alert_s | first alert − labelled start: mean, median, max. It includes the window by design, so it is ≥ 2 s when the window is 2 s. |

These are reported overall and per type (`no_helmet`, `no_vest`), with the
configuration used: window, clear time, tolerance, tracker, thresholds,
weights and whether the person model gave pose keypoints.

## 4. What to report for a model change

1. `metrics.json` for the run (val and test, same split as the baseline).
2. Event metrics on the same labelled videos as the baseline, with the
   default pipeline settings.
3. Any setting changed from the defaults (window, clear time, thresholds,
   tracker), with both before and after numbers.

## 5. Known gaps

- No labelled test videos are in the repository yet, so no event-level
  numbers exist for the current models.
- The detector metrics in `docs/research-log.md` predate this protocol and
  come from random splits. Treat them as upper bounds.
- The pose head and torso regions are used only when the person model is a
  `-pose` model (`PERSON_MODEL_PATH`). Event metrics should state which one
  was used.
