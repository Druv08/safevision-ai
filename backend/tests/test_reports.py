"""Dashboard aggregates (zone, shift, type, presence rate) and the weekly report."""

from datetime import date, datetime, timedelta, timezone

from fake_supabase import VIEWER

from config import settings
from services import db, reports
from services import violations_service as vs
from services.pipeline import Observation

IST = settings.site_timezone


def at(day, hh, mm=0):
    """An instant given in site time (Asia/Kolkata in the tests)."""
    return datetime(2026, 10, day, hh, mm, tzinfo=IST)


def test_shifts_follow_site_time_and_wrap_midnight():
    assert reports.shift_of(at(12, 6)) == "A" and reports.shift_of(at(12, 13, 59)) == "A"
    assert reports.shift_of(at(12, 14)) == "B"
    assert reports.shift_of(at(12, 23)) == "C" and reports.shift_of(at(13, 2)) == "C"


def test_summary_by_zone_shift_type_with_presence_rates(sb):
    cam = db.insert("cameras", {"name": "Gate 2", "url": "rtsp://c/1", "sample_fps": 5, "default_policy": "both",
                                "enabled": True})[0]
    zone = db.insert("zones", {"camera_id": cam["id"], "name": "Scaffold", "policy": "both",
                               "polygon": [[0, 0], [1, 0], [1, 1]]})[0]
    for t, vtype, z in [(at(12, 9), "no_helmet", zone["id"]), (at(12, 10), "no_vest", zone["id"]),
                        (at(12, 23, 30), "no_helmet", None), (at(13, 1), "zone_intrusion", zone["id"])]:
        vs.create_violation(vtype, 0.8, "camera", None, "m1", created_at=t, started_at=t, camera_id=cam["id"],
                            zone_id=z)
    vs.create_violation("no_vest", 0.8, "video", None, "m2", created_at=at(12, 15))  # an upload, no camera
    vs.create_violation("no_vest", 0.8, "video", None, "m2", created_at=at(20, 9))  # outside the range
    vs.record_observations([Observation(1, "helmet", "compliant", 9, 0, 0, 0, 1),
                            Observation(2, "helmet", "compliant", 9, 0, 0, 0, 1),
                            Observation(3, "helmet", "violation", 1, 9, 0, 0, 1),
                            Observation(4, "vest", "unknown", 0, 0, 9, 0, 1)], "camera", "m1")
    for o in sb.tables["observations"]:  # recorded "now"; pin them inside the range
        o["created_at"] = at(12, 11).isoformat()

    s = reports.summary(at(12, 0), at(14, 0))
    assert s["total"] == 5
    assert s["by_type"] == {"no_helmet": 2, "no_vest": 2, "zone_intrusion": 1}
    zones = {(g["camera"], g["zone"]): g for g in s["by_zone"]}
    assert zones[("Gate 2", "Scaffold")]["total"] == 3 and zones[("Gate 2", "Scaffold")]["zone_intrusion"] == 1
    assert zones[("Gate 2", "Outside zones")]["no_helmet"] == 1
    assert zones[("Uploads (no camera)", None)]["no_vest"] == 1
    assert s["by_zone"][0]["zone"] == "Scaffold"  # most violations first

    shifts = {x["shift"]: x for x in s["by_shift"]}
    assert (shifts["A"]["total"], shifts["B"]["total"], shifts["C"]["total"]) == (2, 1, 2)  # 23:30 and 01:00 are C
    assert shifts["A"]["hours"] == "06:00–14:00" and "Outside shifts" not in shifts
    assert s["presence"]["helmet"] == {"compliant": 2, "violation": 1, "unknown": 0, "rate": 0.6667}
    assert s["presence"]["vest"]["rate"] is None  # nobody's vest was ever seen: no rate, not 0 %

    days = s["trend"]["points"]
    assert [d["key"] for d in days] == ["2026-10-12", "2026-10-13"]
    assert days[0]["no_helmet"] == 2 and days[1]["zone_intrusion"] == 1
    assert s["model_versions"] == ["m1", "m2"]


def test_hourly_trend_is_zero_filled_in_site_time(sb):
    vs.create_violation("no_vest", 0.8, "camera", None, "m1", created_at=at(12, 10, 15))
    s = reports.summary(at(12, 8), at(12, 12), bucket="hour")
    assert [(p["key"], p["no_vest"]) for p in s["trend"]["points"]] == [
        ("2026-10-12T08", 0), ("2026-10-12T09", 0), ("2026-10-12T10", 1), ("2026-10-12T11", 0)]


def test_review_status_and_causes_are_counted(sb):
    a = vs.create_violation("no_helmet", 0.8, "camera", None, "m1", created_at=at(12, 9))
    vs.create_violation("no_helmet", 0.8, "camera", None, "m1", created_at=at(12, 9))
    vs.set_status(a["id"], "action_taken", None, "issued helmet", "ppe_not_issued")
    s = reports.summary(at(12, 0), at(13, 0))
    assert s["by_status"] == {"new": 1, "acknowledged": 0, "action_taken": 1, "closed": 0}
    assert s["by_cause"] == {"ppe_not_issued": 1}


def test_weekly_report_is_aggregate_html_and_audited(client, sb):
    v = vs.create_violation("no_helmet", 0.8, "camera", "2026/10/06/abc.jpg", "m1", created_at=at(6, 9))
    vs.set_status(v["id"], "action_taken", None, "Worker's name here", "ppe_not_issued")
    vs.create_violation("no_vest", 0.8, "camera", None, "m1", created_at=at(1, 9))  # previous week

    r = client.get("/reports/weekly?week_start=2026-10-05", headers=VIEWER)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert 'filename="safevision-week-2026-10-05.html"' in r.headers["content-disposition"]
    page = r.text
    assert "05 Oct 2026 – 11 Oct 2026" in page
    for section in ("Overview", "By zone", "By shift", "Review", "Causes recorded by reviewers", "By day"):
        assert f"<h2>{section}</h2>" in page
    assert "PPE not issued: 1." in page and "coaching, not punishment" in page
    assert "<tr><td>Violations recorded</td><td>1</td><td>1</td></tr>" in page  # this week vs previous
    assert "abc.jpg" not in page and "Worker&#x27;s name" not in page  # no images, no notes
    assert sb.tables["audit_log"][-1]["action"] == "weekly_report"


def test_weekly_report_defaults_to_last_complete_week():
    assert reports.last_week_start(date(2026, 10, 13)) == date(2026, 10, 5)  # a Tuesday -> previous Monday
    assert reports.last_week_start(date(2026, 10, 12)) == date(2026, 10, 5)  # a Monday -> the week before


def test_summary_api_for_viewers(client, sb):
    vs.create_violation("no_vest", 0.8, "camera", None, "m1")
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = client.get("/reports/summary", params={"date_from": since}, headers=VIEWER)
    assert r.status_code == 200 and r.json()["total"] == 1 and r.json()["timezone"] == "Asia/Kolkata"
