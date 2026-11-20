"""Turn raw RFC 822 messages into the fields TermPilot stores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime

from bs4 import BeautifulSoup

from termpilot.clock import as_utc

PREVIEW_LENGTH = 180


@dataclass
class ParsedMail:
    uid: str
    message_id: str | None
    subject: str | None
    sender: str | None
    recipients: str | None
    cc: str | None
    received_at: datetime | None
    preview: str | None
    body_text: str | None
    body_html: str | None
    seen: bool
    has_attachments: bool


def decode_words(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (UnicodeDecodeError, LookupError, ValueError):
        return value.strip()


def format_addresses(value: str | None) -> str:
    people = []
    for name, address in getaddresses([value]) if value else []:
        name = decode_words(name)
        if name and address:
            people.append(f"{name} <{address}>")
        elif address or name:
            people.append(address or name)
    return ", ".join(people)


def html_to_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text("\n", strip=True) if html else ""


def _received_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return as_utc(parsedate_to_datetime(raw))
    except (TypeError, ValueError, IndexError):
        return None


def _bodies(message: EmailMessage) -> tuple[str, str, bool]:
    plain: list[str] = []
    html: list[str] = []
    attachments = False
    for part in message.walk():
        if part.is_multipart():
            continue
        if part.get_filename() or part.get_content_disposition() == "attachment":
            attachments = True
            continue
        kind = part.get_content_type()
        if kind not in ("text/plain", "text/html"):
            continue
        try:
            content = part.get_content()
        except (LookupError, UnicodeDecodeError):
            payload = part.get_payload(decode=True) or b""
            content = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        content = str(content).strip()
        if content:
            (plain if kind == "text/plain" else html).append(content)
    text = "\n\n".join(plain)
    markup = "\n".join(html)
    return (text or html_to_text(markup)), markup, attachments


def parse_message(uid: str, raw: bytes, flags: str = "") -> ParsedMail:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    text, markup, attachments = _bodies(message)  # type: ignore[arg-type]
    preview = " ".join(text.split())
    if len(preview) > PREVIEW_LENGTH:
        preview = preview[: PREVIEW_LENGTH - 1].rstrip() + "…"
    return ParsedMail(
        uid=uid,
        message_id=(message.get("Message-ID") or "").strip() or None,
        subject=decode_words(message.get("Subject")) or None,
        sender=format_addresses(message.get("From")) or None,
        recipients=format_addresses(message.get("To")) or None,
        cc=format_addresses(message.get("Cc")) or None,
        received_at=_received_at(message.get("Date")),
        preview=preview or None,
        body_text=text or None,
        body_html=markup or None,
        seen="\\Seen" in flags,
        has_attachments=attachments,
    )


def normalise_recipients(values: list[str]) -> list[str]:
    """Deduplicated bare addresses; raises ``ValueError`` on anything malformed."""
    addresses = [address.strip() for _, address in getaddresses([v for v in values if v and v.strip()])]
    for address in addresses:
        local, _, domain = address.partition("@")
        if not local or "." not in domain:
            raise ValueError(f"{address or '(empty)'} is not a valid email address.")
    return list(dict.fromkeys(addresses))
