"""
Persistent person IDs across frames, using the trackers built into Ultralytics.

The tracker is kept separate from the YOLO model (Ultralytics' `model.track()`
stores tracker state inside the model), so one loaded model can serve many
independent videos, each with its own PersonTracker.
"""

import numpy as np


class _Dets:
    """The slice of an Ultralytics `Boxes` object that BYTETracker / BOTSORT read."""

    def __init__(self, xyxy: np.ndarray, conf: np.ndarray):
        self.xyxy = xyxy
        self.conf = conf
        self.cls = np.zeros(len(conf), dtype=np.float32)

    @property
    def xywh(self) -> np.ndarray:
        x1, y1, x2, y2 = self.xyxy.T
        return np.stack([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], axis=1)

    def __len__(self) -> int:
        return len(self.conf)

    def __getitem__(self, idx) -> "_Dets":
        return _Dets(self.xyxy[idx], self.conf[idx])


def _iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise IoU between (n,4) and (m,4) xyxy arrays."""
    ix1 = np.maximum(a[:, None, 0], b[None, :, 0])
    iy1 = np.maximum(a[:, None, 1], b[None, :, 1])
    ix2 = np.minimum(a[:, None, 2], b[None, :, 2])
    iy2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9)


class PersonTracker:
    """Assigns `track_id` to Person objects frame by frame (ByteTrack or BoT-SORT)."""

    def __init__(self, kind: str = "bytetrack"):
        from ultralytics.trackers.bot_sort import BOTSORT
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.utils import YAML, IterableSimpleNamespace
        from ultralytics.utils.checks import check_yaml

        trackers = {"bytetrack": BYTETracker, "botsort": BOTSORT}
        if kind not in trackers:
            raise ValueError(f"tracker must be one of {sorted(trackers)}, got {kind!r}")
        cfg = IterableSimpleNamespace(**YAML.load(check_yaml(f"{kind}.yaml")))
        if kind == "botsort":
            cfg.with_reid = False  # ReID needs extra weights; motion + IoU only
        self._tracker = trackers[kind](args=cfg)

    def update(self, persons: list, frame: np.ndarray | None = None) -> None:
        """Set `track_id` on each person the tracker confirms this frame (others stay None)."""
        for p in persons:
            p.track_id = None
        boxes = np.array([p.box for p in persons], dtype=np.float32).reshape(-1, 4)
        conf = np.array([p.conf for p in persons], dtype=np.float32)
        tracks = self._tracker.update(_Dets(boxes, conf), frame)
        if len(tracks) == 0 or len(persons) == 0:
            return
        # Track rows are [x1, y1, x2, y2, id, score, cls, idx]; match back to our
        # detections by IoU (the tracker's own idx is relative to a filtered subset).
        iou = _iou(tracks[:, :4], boxes)
        for t in np.argsort(-iou.max(axis=1)):
            d = int(iou[t].argmax())
            if iou[t, d] >= 0.5 and persons[d].track_id is None:
                persons[d].track_id = int(tracks[t, 4])
