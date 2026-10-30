import os
import asyncio
import smtplib
from email.message import EmailMessage
import re
import ipaddress
import logging
import httpx
from html.parser import HTMLParser
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()
logger = logging.getLogger(__name__)
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "emergent").strip().lower()
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "DNS Energy")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


def _send_smtp(to: str, subject: str, html: str, reply_to: str | None) -> str:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ["SMTP_FROM_EMAIL"]
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{EMAIL_FROM_NAME} <{sender}>"
    message["To"] = to
    effective_reply = reply_to or EMAIL_REPLY_TO
    if effective_reply:
        message["Reply-To"] = effective_reply
    message.set_content("Acest mesaj conține conținut HTML. Deschideți-l într-un client de e-mail compatibil.")
    message.add_alternative(html, subtype="html")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    return "smtp-accepted"


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None) -> str | None:
    _assert_safe_email(subject, html)
    try:
        if EMAIL_PROVIDER == "smtp":
            return await asyncio.to_thread(_send_smtp, to, subject, html, reply_to)
        if EMAIL_PROVIDER != "emergent":
            raise RuntimeError("EMAIL_PROVIDER must be 'emergent' or 'smtp'")
        if not EMAIL_KEY:
            raise RuntimeError("EMERGENT_EMAIL_KEY is required while EMAIL_PROVIDER=emergent")
        payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
        if reply_to or EMAIL_REPLY_TO:
            payload["contact_email"] = reply_to or EMAIL_REPLY_TO
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            code = e.response.json().get("code", "")
        except ValueError:
            code = ""
        if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning(f"Email paused: {code} ({e.response.status_code}): {e.response.json().get('message', '')}")
            raise HTTPException(status_code=503, detail="Trimiterea e-mailului este temporar indisponibilă")
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail="E-mailul nu a putut fi trimis")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        raise HTTPException(status_code=500, detail="E-mailul nu a putut fi trimis")
