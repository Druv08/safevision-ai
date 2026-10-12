"""Alert de-duplication, templates per recipient, channels/providers, and the review workflow."""

import hashlib
import hmac
import json
import logging
import threading
import urllib.parse

import pytest
from fake_supabase import ADMIN, VIEWER

from services import alerts, db
from services import violations_service as vs
from services.pipeline import Episode


@pytest.fixture
def sent(monkeypatch):
    """Every HTTP POST the channels make, instead of the network."""
    calls = []
    monkeypatch.setattr(alerts, "_post", lambda url, body, headers: calls.append((url, body, headers)))
    monkeypatch.setattr(alerts.channels["whatsapp"], "provider", None)
    for k in ("WHATSAPP_PROVIDER", "WHATSAPP_META_TOKEN", "WHATSAPP_META_PHONE_NUMBER_ID", "TWILIO_ACCOUNT_SID",
              "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "ALERT_WEBHOOK_SECRET"):
        monkeypatch.delenv(k, raising=False)
    return calls


def violation(**kw):
    return vs.create_violation("no_helmet", 0.9, "camera", None, "m1",
                               started_at="2026-10-12T04:00:00+00:00", **kw)  # 09:30 in Asia/Kolkata


def hook(name="Site office", address="https://hooks.example/sv", language="en"):
    return alerts.create_recipient(name, "webhook", address, language)


# ---------------------------------------------------------------------------
# De-duplication
# ---------------------------------------------------------------------------
def test_one_alert_per_episode_per_recipient(sb, sent):
    hook("A"), hook("B", "https://b.example/x")
    v = violation()
    assert [a["status"] for a in alerts.notify(v)] == ["sent", "sent"]
    assert alerts.notify(v) == [] and alerts.notify(v) == []  # retries / repeats send nothing
    assert len(sent) == 2 and len(sb.tables["alerts"]) == 2

    hook("C", "https://c.example/x")  # a recipient added later gets it once
    assert len(alerts.notify(v)) == 1 and len(sent) == 3
    assert len(alerts.notify(violation())) == 3  # a new episode is a new alert


def test_concurrent_notifies_send_once(local_mode, sent):
    hook()
    v = violation()
    start = threading.Barrier(8)

    def go():
        start.wait()
        alerts.notify(v)

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(sent) == 1
    assert [a["status"] for a in db.select("alerts")] == ["sent"]


def test_episode_end_update_does_not_alert_again(sb, sent, set_settings, monkeypatch):
    set_settings(alert_sources=("camera",))
    monkeypatch.setattr(alerts._pool, "submit", lambda fn, *a: fn(*a))  # run inline
    hook()
    row = vs.save_episode(Episode("no_vest", 3, 0, 2, 2, 0.8, (0, 0, 8, 8)), "camera", "m1", camera_id=None)
    vs.set_episode_end(row["id"], 9.0)
    vs.save_episode(Episode("no_vest", 4, 0, 2, 2, 0.8, (0, 0, 8, 8)), "video", "m1")  # uploads don't alert
    assert len(sent) == 1


def test_disabled_recipients_get_nothing(sb, sent):
    r = hook()
    alerts.update_recipient(r["id"], enabled=False)
    assert alerts.notify(violation()) == [] and sent == []


# ---------------------------------------------------------------------------
# Templates and channels
# ---------------------------------------------------------------------------
def test_template_language_is_chosen_per_recipient(sb, sent):
    cam = db.insert("cameras", {"name": "Gate 2", "url": "rtsp://cam/1", "sample_fps": 5, "default_policy": "both",
                                "enabled": False})[0]
    hook("English", "https://en.example/x", "en")
    hook("हिन्दी", "https://hi.example/x", "hi")
    alerts.notify(violation(camera_id=cam["id"]))
    en, hi = (json.loads(body) for _, body, _ in sent)

    assert en["text"].startswith("SafeVision: Helmet not detected at Gate 2, 12 Oct 2026, 09:30 IST.")
    assert hi["text"].startswith("SafeVision: Gate 2 पर हेलमेट नहीं दिखा, 12-10-2026, 09:30 IST।")
    assert "कृपया मौके पर जाँच करें" in hi["text"]
    for msg in (en, hi):
        assert msg["link"] == f"https://safevision.example/violations?id={msg['violation_id']}"
        assert msg["link"] in msg["text"] and msg["camera"] == "Gate 2"
        assert "screenshot" not in json.dumps(msg)  # no image or storage key in a message


def test_whatsapp_without_credentials_logs_and_does_not_fail(sb, sent, caplog):
    alerts.create_recipient("Supervisor", "whatsapp", "+919812345678", "hi")
    with caplog.at_level(logging.WARNING, logger="services.alerts"):
        out = alerts.notify(violation())
    assert [(a["status"], a["error"]) for a in out] == [("logged", None)]
    assert sent == [] and "हेलमेट नहीं दिखा" in caplog.text
    assert "9812345678" not in caplog.text and "…5678" in caplog.text  # the number is masked in logs


def test_a_failing_channel_is_recorded_and_others_still_send(sb, sent, monkeypatch):
    def flaky(url, body, headers):
        if "down" in url:
            raise OSError("connection refused")
        sent.append(url)

    monkeypatch.setattr(alerts, "_post", flaky)
    hook("Down", "https://down.example/x")
    hook("Up", "https://up.example/x")
    out = {a["recipient_name"]: a for a in alerts.notify(violation())}
    assert out["Down"]["status"] == "failed" and "connection refused" in out["Down"]["error"]
    assert out["Up"]["status"] == "sent" and sent == ["https://up.example/x"]


def test_webhook_is_signed_when_a_secret_is_set(sb, sent, monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_SECRET", "s3cret")
    hook()
    alerts.notify(violation())
    _, body, headers = sent[0]
    assert headers["X-SafeVision-Signature"] == "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()


def test_meta_and_twilio_providers_build_the_documented_requests(sb, sent, monkeypatch):
    msg = alerts.render({"id": "v1", "type": "no_vest", "created_at": "2026-10-12T04:00:00+00:00"}, "en")
    monkeypatch.setenv("WHATSAPP_META_TOKEN", "meta-token")
    monkeypatch.setenv("WHATSAPP_META_PHONE_NUMBER_ID", "1234567")
    assert alerts.WhatsAppChannel().send({"address": "+919812345678"}, msg) == "sent"
    url, body, headers = sent[-1]
    assert url == "https://graph.facebook.com/v21.0/1234567/messages"
    assert headers["Authorization"] == "Bearer meta-token"
    assert json.loads(body) == {"messaging_product": "whatsapp", "to": "919812345678", "type": "text",
                                "text": {"body": msg.text}}

    monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tw-token")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")
    assert alerts.whatsapp_provider().name == "twilio"
    alerts.WhatsAppChannel().send({"address": "+919812345678"}, msg)
    url, body, headers = sent[-1]
    assert url == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    form = urllib.parse.parse_qs(body.decode())
    assert form == {"From": ["whatsapp:+14155238886"], "To": ["whatsapp:+919812345678"], "Body": [msg.text]}


def test_provider_named_without_credentials_falls_back_to_the_log(monkeypatch, sent):
    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
    assert alerts.whatsapp_provider().name == "log"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_recipient_api_validates_and_is_admin_only(client, sb, sent):
    good = {"name": "Supervisor", "channel": "whatsapp", "address": "+919812345678", "language": "hi"}
    assert client.post("/alerts/recipients", json=good, headers=VIEWER).status_code == 403
    assert client.get("/alerts/recipients", headers=VIEWER).status_code == 403
    bad_phone = client.post("/alerts/recipients", json={**good, "address": "98123 45678"}, headers=ADMIN)
    assert bad_phone.status_code == 422 and "+919812345678" in bad_phone.json()["detail"]
    bad_url = client.post("/alerts/recipients", json={**good, "channel": "webhook", "address": "ftp://x"},
                          headers=ADMIN)
    assert bad_url.status_code == 422

    r = client.post("/alerts/recipients", json=good, headers=ADMIN)
    assert r.status_code == 201
    rid = r.json()["id"]
    listing = client.get("/alerts/recipients", headers=ADMIN).json()
    assert listing["whatsapp_provider"] == "log" and listing["recipients"][0]["language"] == "hi"
    assert client.patch(f"/alerts/recipients/{rid}", json={"address": "nope"}, headers=ADMIN).status_code == 422

    test = client.post(f"/alerts/recipients/{rid}/test", headers=ADMIN).json()
    assert test == {"status": "logged", "error": None}
    assert client.delete(f"/alerts/recipients/{rid}", headers=ADMIN).status_code == 200
    assert [a["action"] for a in sb.tables["audit_log"]] == [
        "alert_recipient_create", "alert_test", "alert_recipient_delete"]
    assert "9812345678" not in json.dumps(sb.tables["audit_log"])  # no phone numbers in the audit log


def test_alert_log_lists_deliveries(client, sb, sent):
    hook()
    alerts.notify(violation())
    rows = client.get("/alerts", headers=ADMIN).json()["alerts"]
    assert [(a["recipient_name"], a["status"]) for a in rows] == [("Site office", "sent")]


# ---------------------------------------------------------------------------
# Review workflow: acknowledge, action taken (with a note), close; causes
# ---------------------------------------------------------------------------
def test_review_workflow_with_cause_ppe_not_issued(client, sb):
    v = violation()
    url = f"/violations/{v['id']}"
    assert client.patch(url, json={"status": "acknowledged"}, headers=ADMIN).json()["acknowledged_by"] == sb.admin_id

    r = client.patch(url, json={"status": "action_taken"}, headers=ADMIN)
    assert r.status_code == 422 and "note" in r.json()["detail"]
    r = client.patch(url, json={"status": "action_taken", "note": "Gate store had no helmets; issued 5",
                                "cause": "ppe_not_issued"}, headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["cause"], body["action_taken_by"]) == ("action_taken", "ppe_not_issued", sb.admin_id)
    assert client.patch(url, json={"status": "closed", "cause": "made_up"}, headers=ADMIN).status_code == 422
    assert client.patch(url, json={"status": "closed"}, headers=ADMIN).json()["status"] == "closed"
    assert client.get("/violations?status=action_taken", headers=VIEWER).json()["count"] == 0
    assert [a["action"] for a in sb.tables["audit_log"]] == ["acknowledged", "action_taken", "closed"]
