"""
Alerts: one message per violation episode to every enabled recipient.

A recipient has a channel, an address and a language (English or Hindi):

  whatsapp  address = phone number in E.164 form (+919812345678); sent through
            a WhatsAppProvider: Meta WhatsApp Cloud API or Twilio, chosen from
            the environment. With no credentials the message is written to the
            log instead and the alert is recorded as "logged", never failed.
  webhook   address = https URL; the alert is POSTed as JSON, signed with
            HMAC-SHA256 (X-SafeVision-Signature) when ALERT_WEBHOOK_SECRET is set.

Any object with `send(recipient, message) -> "sent" | "logged"` can be a channel.

De-duplication: before sending, a row (violation_id, recipient_id) is inserted
into `alerts`. The table's unique constraint lets exactly one attempt through,
so a retry, a restart or two threads can never send the same alert twice. One
violation row is one episode (pipeline.py), so this is one alert per episode
per recipient. Alerts go out for sources in ALERT_SOURCES (default: camera).

Messages carry no image: the link opens the record for signed-in users only.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from config import settings
from services import db

log = logging.getLogger(__name__)

LANGUAGES = ("en", "hi")
CHANNELS = ("whatsapp", "webhook")
TIMEOUT_S = 10

# PPE *presence detection*: the model reports what it did not see, not what a person did.
TYPE_TEXT = {
    "en": {"no_helmet": "Helmet not detected", "no_vest": "Safety vest not detected",
           "zone_intrusion": "Person in a no-entry zone"},
    "hi": {"no_helmet": "हेलमेट नहीं दिखा", "no_vest": "सेफ़्टी वेस्ट नहीं दिखी",
           "zone_intrusion": "प्रतिबंधित क्षेत्र में व्यक्ति"},
}
TEMPLATES = {
    "en": "SafeVision: {what} at {where}, {when}.\n"
          "Please check on site and help the worker get the right PPE.\n"
          "Record: {link}",
    "hi": "SafeVision: {where} पर {what}, {when}।\n"
          "कृपया मौके पर जाँच करें और कर्मचारी को सही PPE दिलाने में मदद करें।\n"
          "रिकॉर्ड: {link}",
}
UPLOAD_PLACE = {"en": "an uploaded file", "hi": "अपलोड की गई फ़ाइल"}
TIME_FORMAT = {"en": "%d %b %Y, %H:%M %Z", "hi": "%d-%m-%Y, %H:%M %Z"}


@dataclass
class Message:
    text: str
    link: str
    payload: dict  # what a webhook receives


def render(violation: dict, language: str, camera: str | None = None, zone: str | None = None) -> Message:
    lang = language if language in LANGUAGES else "en"
    when = datetime.fromisoformat(violation.get("started_at") or violation["created_at"]).astimezone(
        settings.site_timezone)
    where = " / ".join(x for x in (camera, zone) if x) or UPLOAD_PLACE[lang]
    link = f"{settings.app_base_url}/violations?id={violation['id']}"
    what = TYPE_TEXT[lang].get(violation["type"], violation["type"])
    text = TEMPLATES[lang].format(what=what, where=where, when=when.strftime(TIME_FORMAT[lang]), link=link)
    payload = {
        "event": "violation", "violation_id": violation["id"], "type": violation["type"], "camera": camera,
        "zone": zone, "time": when.isoformat(), "confidence": violation.get("confidence"),
        "source": violation.get("source"), "link": link, "language": lang, "text": text,
    }
    return Message(text, link, payload)


# ---------------------------------------------------------------------------
# HTTP (stdlib only; tests replace _post)
# ---------------------------------------------------------------------------
def _post(url: str, body: bytes, headers: dict) -> None:
    """POST; raises on a network error or a non-2xx answer."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 (scheme checked on save)
        r.read(4096)


# ---------------------------------------------------------------------------
# WhatsApp providers
# ---------------------------------------------------------------------------
class WhatsAppProvider(Protocol):
    name: str

    def send_text(self, to: str, text: str) -> str:
        """Send one text message to an E.164 number. Returns "sent" (or "logged"); raises on failure."""


def _mask(number: str) -> str:
    return f"…{number[-4:]}"


class LogProvider:
    """No credentials configured: write the message to the log and carry on."""

    name = "log"

    def send_text(self, to: str, text: str) -> str:
        log.warning("WhatsApp is not configured; alert for %s written to the log only:\n%s", _mask(to), text)
        return "logged"


class MetaCloudProvider:
    """WhatsApp Cloud API. Needs WHATSAPP_META_TOKEN and WHATSAPP_META_PHONE_NUMBER_ID.

    Free-form text is delivered only inside a 24-hour window after the recipient
    last messaged your number; outside it Meta requires an approved template.
    """

    name = "meta"

    def __init__(self, token: str, phone_number_id: str, api_version: str = "v21.0"):
        self.url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self._token = token

    def send_text(self, to: str, text: str) -> str:
        body = {"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "text", "text": {"body": text}}
        _post(self.url, json.dumps(body).encode(),
              {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"})
        return "sent"


class TwilioProvider:
    """Twilio WhatsApp. Needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM (+E.164).

    Same 24-hour rule as Meta: outside a session Twilio needs an approved
    content template (the sandbox works for testing).
    """

    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        self._auth = b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        self.from_number = from_number

    def send_text(self, to: str, text: str) -> str:
        form = urllib.parse.urlencode({"From": f"whatsapp:{self.from_number}", "To": f"whatsapp:{to}", "Body": text})
        _post(self.url, form.encode(),
              {"Authorization": f"Basic {self._auth}", "Content-Type": "application/x-www-form-urlencoded"})
        return "sent"


def whatsapp_provider() -> WhatsAppProvider:
    """WHATSAPP_PROVIDER=meta|twilio, or whichever has credentials set; the log when none has."""
    env = {k: os.getenv(k, "").strip() for k in (
        "WHATSAPP_PROVIDER", "WHATSAPP_META_TOKEN", "WHATSAPP_META_PHONE_NUMBER_ID",
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")}
    choice = env["WHATSAPP_PROVIDER"].lower()
    meta = env["WHATSAPP_META_TOKEN"] and env["WHATSAPP_META_PHONE_NUMBER_ID"]
    twilio = env["TWILIO_ACCOUNT_SID"] and env["TWILIO_AUTH_TOKEN"] and env["TWILIO_WHATSAPP_FROM"]
    if choice in ("", "meta") and meta:
        return MetaCloudProvider(env["WHATSAPP_META_TOKEN"], env["WHATSAPP_META_PHONE_NUMBER_ID"])
    if choice in ("", "twilio") and twilio:
        return TwilioProvider(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"], env["TWILIO_WHATSAPP_FROM"])
    if choice:
        log.warning("WHATSAPP_PROVIDER=%s but its credentials are not all set: alerts go to the log", choice)
    return LogProvider()


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
class Channel(Protocol):
    def send(self, recipient: dict, message: Message) -> str:
        """Deliver one message. Returns "sent" or "logged"; raises on failure."""


class WhatsAppChannel:
    def __init__(self, provider: WhatsAppProvider | None = None):
        self.provider = provider

    def send(self, recipient: dict, message: Message) -> str:
        return (self.provider or whatsapp_provider()).send_text(recipient["address"], message.text)


class WebhookChannel:
    def send(self, recipient: dict, message: Message) -> str:
        body = json.dumps(message.payload, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json; charset=utf-8", "User-Agent": "SafeVision-Alerts/1"}
        secret = os.getenv("ALERT_WEBHOOK_SECRET", "")
        if secret:
            headers["X-SafeVision-Signature"] = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        _post(recipient["address"], body, headers)
        return "sent"


channels: dict[str, Channel] = {"whatsapp": WhatsAppChannel(), "webhook": WebhookChannel()}


# ---------------------------------------------------------------------------
# Recipients
# ---------------------------------------------------------------------------
_E164 = re.compile(r"\+[1-9]\d{6,14}")


def validate_recipient(channel: str, address: str, language: str) -> None:
    """Raises ValueError with a readable message."""
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {', '.join(CHANNELS)}")
    if language not in LANGUAGES:
        raise ValueError(f"language must be one of {', '.join(LANGUAGES)}")
    if channel == "whatsapp" and not _E164.fullmatch(address):
        raise ValueError("WhatsApp number must be in international form, e.g. +919812345678")
    if channel == "webhook":
        u = urllib.parse.urlsplit(address)
        allowed = ("https",) if settings.is_production else ("https", "http")
        if u.scheme not in allowed or not u.hostname:
            raise ValueError(f"webhook URL must start with {' or '.join(s + '://' for s in allowed)}")


def list_recipients() -> list[dict]:
    return db.select("alert_recipients")


def create_recipient(name: str, channel: str, address: str, language: str = "en", enabled: bool = True) -> dict:
    validate_recipient(channel, address, language)
    return db.insert("alert_recipients", {"name": name, "channel": channel, "address": address,
                                          "language": language, "enabled": enabled})[0]


def update_recipient(recipient_id: str, **changes) -> dict | None:
    rows = db.select("alert_recipients", id=recipient_id)
    if not rows:
        return None
    merged = {**rows[0], **{k: v for k, v in changes.items() if v is not None}}
    validate_recipient(merged["channel"], merged["address"], merged["language"])
    return db.update("alert_recipients", recipient_id, {k: v for k, v in changes.items() if v is not None})


def delete_recipient(recipient_id: str) -> None:
    db.delete("alert_recipients", id=recipient_id)


def recent_alerts(limit: int = 50) -> list[dict]:
    return db.select("alerts", desc=True, limit=limit)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------
def _places(violation: dict) -> tuple[str | None, str | None]:
    names = []
    for table, key in (("cameras", "camera_id"), ("zones", "zone_id")):
        rows = db.select(table, id=violation[key]) if violation.get(key) else []
        names.append(rows[0]["name"] if rows else None)
    return names[0], names[1]


def _deliver(recipient: dict, message: Message) -> tuple[str, str | None]:
    try:
        return channels[recipient["channel"]].send(recipient, message), None
    except Exception as e:  # network, HTTP 4xx/5xx, bad credentials: recorded, never raised
        log.warning("alert to %s (%s) failed: %s", recipient.get("name"), recipient["channel"], e)
        return "failed", f"{type(e).__name__}: {e}"[:300]


def notify(violation: dict) -> list[dict]:
    """Send this violation to every enabled recipient that has not had it yet. Returns the alert rows written."""
    recipients = db.select("alert_recipients", enabled=True)
    if not recipients:
        return []
    camera, zone = _places(violation)
    out = []
    for r in recipients:
        try:  # claim first: the unique (violation_id, recipient_id) makes this the de-duplication
            claim = db.insert("alerts", {"violation_id": violation["id"], "recipient_id": r["id"],
                                         "recipient_name": r["name"], "channel": r["channel"], "status": "sending"})[0]
        except db.Conflict:
            continue
        status, error = _deliver(r, render(violation, r["language"], camera, zone))
        changes = {"status": status, "error": error}
        if status != "failed":
            changes["sent_at"] = datetime.now(timezone.utc).isoformat()
        out.append(db.update("alerts", claim["id"], changes) or {**claim, **changes})
    return out


# ponytail: in-process pool, lost on a hard kill (the claim row stays "sending");
# move to a queue table + worker if alerts must survive crashes.
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alerts")


def _notify_logged(violation: dict) -> None:
    try:
        notify(violation)
    except Exception:  # alerts must never break detection; migration 0004 missing, DB down, ...
        log.exception("could not send alerts for violation %s", violation.get("id"))


def notify_async(violation: dict) -> None:
    """Called when a violation is saved; returns at once. Only sources in ALERT_SOURCES alert."""
    if violation.get("source") in settings.alert_sources:
        _pool.submit(_notify_logged, violation)


def send_test(recipient: dict) -> tuple[str, str | None]:
    """A sample alert to one recipient (no alerts row; not de-duplicated)."""
    sample = {"id": "00000000-0000-0000-0000-000000000000", "type": "no_helmet", "confidence": 0.9,
              "source": "camera", "created_at": datetime.now(timezone.utc).isoformat()}
    lang = recipient["language"] if recipient["language"] in LANGUAGES else "en"
    zone = {"en": "test message", "hi": "परीक्षण संदेश"}[lang]
    return _deliver(recipient, render(sample, lang, "SafeVision", zone))
