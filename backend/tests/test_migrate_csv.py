import cv2
import numpy as np

from scripts.migrate_csv import migrate


def make_jpeg(path):
    cv2.imwrite(str(path), np.zeros((16, 16, 3), np.uint8))


def test_migrates_both_formats_and_is_idempotent(tmp_path, sb):
    shots = tmp_path / "screenshots"
    shots.mkdir()
    make_jpeg(shots / "a.jpg")
    make_jpeg(shots / "b.jpg")
    make_jpeg(shots / "c.jpg")

    # 8-column header, then headerless backend rows, then a 9-column CLI header and rows.
    csv_text = "\n".join([
        "violation_id,timestamp,source,frame_number,violation_type,severity,confidence,screenshot_path",
        f"aaa111,2026-06-06_23-39-07,0,2,Safety Vest Missing,Medium,0.466,{shots / 'a.jpg'}",
        r"bbb222,2026-08-12_12-48-36,chunk_x.webm,135,Helmet Missing,High,0.853,D:\old\machine\screenshots\b.jpg",
        "violation_id,timestamp,source,frame_number,violation_type,severity,confidence,worker_detected,screenshot_path",
        "ccc333,2026-06-07T10:00:00,0,9,Multiple PPE Missing,Critical,0.700,yes,"
        "ai-model/outputs/violations/screenshots/c.jpg",
        "ddd444,2026-06-07T10:00:05,photo.png,1,Helmet Missing,High,0.500,no,missing.jpg",
        "too,few,columns",
        "eee555,not-a-date,0,1,Helmet Missing,High,0.5,",
    ])
    csv_path = tmp_path / "violations_log.csv"
    csv_path.write_text(csv_text + "\n", encoding="utf-8")

    stats = migrate(csv_path, screenshots_dir=shots)
    assert stats == {"imported": 5, "skipped_existing": 0, "skipped_invalid": 1, "missing_screenshot": 1}

    rows = {r["note"]: r for r in sb.tables["violations"]}
    a = rows["migrated from CSV, legacy id aaa111"]
    assert (a["type"], a["source"], a["confidence"]) == ("no_vest", "camera", 0.466)
    assert a["created_at"].startswith("2026-06-06T23:39:07")

    b = rows["migrated from CSV, legacy id bbb222"]
    assert (b["type"], b["source"]) == ("no_helmet", "video")
    assert b["screenshot_path"] in sb.objects  # found by file name in --screenshots-dir

    assert rows["migrated from CSV, legacy id ccc333 (no_helmet)"]["type"] == "no_helmet"
    assert rows["migrated from CSV, legacy id ccc333 (no_vest)"]["type"] == "no_vest"
    assert rows["migrated from CSV, legacy id ddd444"]["source"] == "image"
    assert rows["migrated from CSV, legacy id ddd444"]["screenshot_path"] is None

    # keys are server-generated; no absolute paths or CSV file names stored
    for r in sb.tables["violations"]:
        key = r["screenshot_path"]
        assert key is None or (":" not in key and "\\" not in key and not key.startswith("/"))
    assert len(sb.objects) == 4  # a, b, and c twice (one object per row)

    again = migrate(csv_path, screenshots_dir=shots)
    assert again["imported"] == 0 and again["skipped_existing"] == 5
    assert len(sb.tables["violations"]) == 5
