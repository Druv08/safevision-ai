"""
Aggregates for the dashboard and the weekly report: violations by zone, shift
and type, review status and causes, and PPE presence rates.

Presence rate per item = people seen wearing it / (wearing + violating); people
whose item was never visible are left out (observations, pipeline.py). Rates
are available overall and per shift, not per zone: an observation covers a
person's whole time in view, across zones.

Shifts and days are in the site's time zone (SITE_TIMEZONE, SHIFTS). A
violation counts in the shift its episode started in.

ponytail: rows for the range are aggregated in Python; fine for tens of
thousands of rows a week. Move to SQL views / an RPC when that gets slow.
"""

import html
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

from config import settings
from services import db
from services.pipeline import TYPE_LABELS

TYPES = tuple(TYPE_LABELS)
ITEMS = ("helmet", "vest")
UNASSIGNED = "Outside shifts"
CAUSE_LABELS = {
    "ppe_not_issued": "PPE not issued",
    "ppe_not_worn": "PPE issued, not worn",
    "ppe_damaged": "PPE damaged or unsuitable",
    "false_detection": "False detection",
    "other": "Other",
}
STATUS_LABELS = {"new": "Awaiting review", "acknowledged": "Acknowledged", "action_taken": "Action taken",
                 "closed": "Closed"}


def shift_of(local: datetime) -> str:
    t = local.time()
    for name, start, end in settings.shifts:
        if (start <= t < end) if start < end else (t >= start or t < end):  # a night shift wraps midnight
            return name
    return UNASSIGNED


def _local(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(settings.site_timezone)


def _rate(n: dict) -> float | None:
    decided = n["compliant"] + n["violation"]
    return round(n["compliant"] / decided, 4) if decided else None


def _buckets(start: datetime, end: datetime, hourly: bool) -> list[str]:
    """Zero-filled bucket keys (local 'YYYY-MM-DD' or 'YYYY-MM-DDTHH') covering [start, end)."""
    keys, t = [], start.astimezone(settings.site_timezone)
    if hourly:
        t = t.replace(minute=0, second=0, microsecond=0)
        while t < end:
            keys.append(t.strftime("%Y-%m-%dT%H"))
            t += timedelta(hours=1)
    else:
        d, last = t.date(), (end - timedelta(microseconds=1)).astimezone(settings.site_timezone).date()
        while d <= last:
            keys.append(d.isoformat())
            d += timedelta(days=1)
    return keys


def summary(date_from: datetime | None, date_to: datetime | None, bucket: str = "day") -> dict:
    rows = db.select("violations", date_from=date_from, date_to=date_to)
    observations = db.select("observations", date_from=date_from, date_to=date_to)
    cameras = {c["id"]: c["name"] for c in db.select("cameras")}
    zones = {z["id"]: z["name"] for z in db.select("zones")}
    zero = dict.fromkeys(TYPES, 0)

    by_zone, by_shift = {}, {}
    for name, start, end in [*settings.shifts, (UNASSIGNED, None, None)]:
        by_shift[name] = {"shift": name, "hours": f"{start:%H:%M}–{end:%H:%M}" if start else None, "total": 0,
                          **zero, "presence": {i: {"compliant": 0, "violation": 0} for i in ITEMS}}
    hourly = bucket == "hour"
    end = date_to or datetime.now(timezone.utc)
    start = date_from or (min((datetime.fromisoformat(r["created_at"]) for r in rows), default=end))
    trend = {k: {"key": k, **zero} for k in _buckets(start, end, hourly)}

    for r in rows:
        cam, zone = r.get("camera_id"), r.get("zone_id")
        g = by_zone.setdefault((cam, zone), {
            "camera_id": cam, "zone_id": zone, "total": 0, **zero,
            "camera": cameras.get(cam, "Deleted camera") if cam else "Uploads (no camera)",
            "zone": zones.get(zone, "Deleted zone") if zone else ("Outside zones" if cam else None),
        })
        g["total"] += 1
        g[r["type"]] += 1
        when = _local(r.get("started_at") or r["created_at"])
        s = by_shift[shift_of(when)]
        s["total"] += 1
        s[r["type"]] += 1
        key = when.strftime("%Y-%m-%dT%H") if hourly else when.date().isoformat()
        if key in trend:
            trend[key][r["type"]] += 1

    presence = {i: {"compliant": 0, "violation": 0, "unknown": 0} for i in ITEMS}
    for o in observations:
        if o["item"] in presence:
            presence[o["item"]][o["outcome"]] += 1
            if o["outcome"] != "unknown":
                by_shift[shift_of(_local(o["created_at"]))]["presence"][o["item"]][o["outcome"]] += 1
    for n in presence.values():
        n["rate"] = _rate(n)
    for s in by_shift.values():
        for n in s["presence"].values():
            n["rate"] = _rate(n)
    def used(s):
        return s["total"] or any(n["compliant"] + n["violation"] for n in s["presence"].values())

    shifts = [s for s in by_shift.values() if s["shift"] != UNASSIGNED or used(s)]

    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "timezone": str(settings.site_timezone),
        "total": len(rows),
        "by_type": {t: sum(r["type"] == t for r in rows) for t in TYPES},
        "by_status": {s: sum(r["status"] == s for r in rows) for s in STATUS_LABELS},
        "by_cause": dict(Counter(r["cause"] for r in rows if r.get("cause"))),
        "by_zone": sorted(by_zone.values(), key=lambda g: -g["total"]),
        "by_shift": shifts,
        "presence": presence,
        "trend": {"bucket": "hour" if hourly else "day", "points": list(trend.values())},
        "model_versions": sorted({r["model_version"] for r in rows if r.get("model_version")}),
    }


# ---------------------------------------------------------------------------
# Weekly report
# ---------------------------------------------------------------------------
def last_week_start(today: date | None = None) -> date:
    """Monday of the last complete week, in the site's time zone."""
    today = today or datetime.now(settings.site_timezone).date()
    return today - timedelta(days=today.weekday() + 7)


def _pct(rate) -> str:
    return "–" if rate is None else f"{rate:.0%}"


def _table(head: list[str], body: list[list], empty: str = "None in this week.") -> str:
    if not body:
        return f"<p class='muted'>{html.escape(empty)}</p>"
    th = "".join(f"<th>{html.escape(h)}</th>" for h in head)
    trs = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>" for row in body)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def weekly_report(week_start: date) -> tuple[str, str]:
    """(HTML, file name) for the 7 days from week_start (site time zone). Aggregates only: no images, no names."""
    tz = settings.site_timezone
    start = datetime.combine(week_start, time(), tz)
    end = start + timedelta(days=7)
    s = summary(start, end)
    prev = summary(start - timedelta(days=7), start)
    labels = [TYPE_LABELS[t][0] for t in TYPES]
    title = f"SafeVision weekly report: {start:%d %b %Y} – {end - timedelta(days=1):%d %b %Y}"

    overview = [
        ["Violations recorded", s["total"], prev["total"]],
        *[[f"{TYPE_LABELS[t][0]}", s["by_type"][t], prev["by_type"][t]] for t in TYPES],
        *[[f"{i.capitalize()} presence rate", _pct(s["presence"][i]["rate"]), _pct(prev["presence"][i]["rate"])]
          for i in ITEMS],
    ]
    zones = [[g["camera"], g["zone"] or "–", g["total"], *[g[t] for t in TYPES]] for g in s["by_zone"]]
    shifts = [[x["shift"], x["hours"] or "–", x["total"], *[x[t] for t in TYPES],
               *[_pct(x["presence"][i]["rate"]) for i in ITEMS]] for x in s["by_shift"]]
    review = [[STATUS_LABELS[k], v] for k, v in s["by_status"].items()]
    causes = [[CAUSE_LABELS.get(k, k), v] for k, v in sorted(s["by_cause"].items(), key=lambda kv: -kv[1])]
    days = [[p["key"], sum(p[t] for t in TYPES), *[p[t] for t in TYPES]] for p in s["trend"]["points"]]
    not_issued = s["by_cause"].get("ppe_not_issued", 0)

    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  body {{ font: 14px/1.5 system-ui, sans-serif; color: #1c1f23; background: #fff; max-width: 60rem;
         margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ font-size: 1.4rem; margin-bottom: .2rem; }} h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: .5rem; }}
  th, td {{ text-align: left; padding: .35rem .6rem; border-bottom: 1px solid #dde1e6; }}
  td:not(:first-child), th:not(:first-child) {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .muted {{ color: #5f6b7a; }} .note {{ background: #f4f6f8; border-left: 3px solid #5f6b7a; padding: .6rem .9rem; }}
  @media print {{ body {{ margin: 0; }} h2 {{ break-after: avoid; }} }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="muted">Times in {html.escape(s["timezone"])}. Generated {datetime.now(tz):%d %b %Y %H:%M}.
Model: {html.escape(", ".join(s["model_versions"]) or "–")}.</p>
<p class="note">These figures come from PPE presence detection: they count what the cameras did not see,
which is not proof of what anyone did, and the model makes mistakes. Use them to find where PPE, training
or site layout needs attention: for coaching, not punishment.</p>
<h2>Overview</h2>{_table(["", "This week", "Previous week"], overview)}
<h2>By zone</h2>{_table(["Camera", "Zone", "Total", *labels], zones)}
<h2>By shift</h2>{_table(["Shift", "Hours", "Total", *labels, "Helmet presence", "Vest presence"], shifts)}
<h2>Review</h2>{_table(["Status", "Records"], review)}
<h2>Causes recorded by reviewers</h2>
{f'<p><strong>PPE not issued: {not_issued}.</strong> These point to supply, not to workers.</p>' if not_issued else ''}
{_table(["Cause", "Records"], causes, "No causes recorded this week.")}
<h2>By day</h2>{_table(["Day", "Total", *labels], days)}
</body></html>"""
    return body, f"safevision-week-{week_start.isoformat()}.html"
