"""DB_DISABLED=true: violations and screenshots round-trip through local_store."""

import dataclasses
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np

import config
from services import local_store, storage_service
from services import violations_service as vs
from services.pipeline import Episode, Observation


def test_local_mode_roundtrip(tmp_path, monkeypatch):
    local = dataclasses.replace(config.settings, db_disabled=True)
    monkeypatch.setattr(vs, "settings", local)
    monkeypatch.setattr(storage_service, "settings", local)
    monkeypatch.setattr(local_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(local_store, "SHOTS_DIR", tmp_path / "shots")
    monkeypatch.setattr(local_store, "_conn", None)

    jpeg = cv2.imencode(".jpg", np.zeros((8, 8, 3), dtype=np.uint8))[1].tobytes()
    a = vs.save_episode(Episode("no_helmet", 3, 1.0, 3.0, 4.5, 0.9, (0, 0, 8, 8), jpeg), "video", "m1")
    vs.save_episode(Episode("no_vest", None, 0.0, 0.0, 0.0, 0.7, (0, 0, 8, 8), jpeg), "camera", "m1", tracked=False)

    assert a["status"] == "new" and a["screenshot_path"]
    assert (a["track_id"], a["episode_start_s"], a["episode_end_s"]) == (3, 1.0, 4.5)
    vs.record_observations([Observation(3, "helmet", "violation", 0, 40, 5, 1.0, 4.5),
                            Observation(4, "helmet", "compliant", 50, 0, 0, 0.0, 5.0)], "video", "m1")
    assert vs.compliance_stats()["helmet"] == {"compliant": 1, "violation": 1, "unknown": 0, "rate": 0.5}
    assert vs.count_by_type() == {"no_helmet": 1, "no_vest": 1, "zone_intrusion": 0}
    rows, total = vs.list_violations(vtype="no_vest")
    assert total == 1 and rows[0]["type"] == "no_vest"
    assert vs.list_violations(q="helmet")[1] == 1
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    assert vs.list_violations(date_from=tomorrow)[1] == 0
    assert vs.list_violations(date_to=tomorrow)[1] == 2

    assert storage_service.create_signed_url(a["screenshot_path"]).startswith("data:image/jpeg;base64,")
    assert vs.set_status(a["id"], "acknowledged", None)["status"] == "acknowledged"

    assert vs.delete_violation(a["id"])["id"] == a["id"]
    assert vs.get_violation(a["id"]) is None
    assert not (tmp_path / "shots" / a["screenshot_path"]).exists()
    assert len(vs.all_violations()) == 1
    local_store._conn.close()
