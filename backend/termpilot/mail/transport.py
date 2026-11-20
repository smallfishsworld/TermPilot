"""Network access to a mailbox, plus an offline stand-in for demo mode."""

from __future__ import annotations

import imaplib
import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Protocol

from termpilot.clock import utcnow
from termpilot.errors import InvalidInput, NotAuthenticated, UpstreamFailure
from termpilot.mail.parsing import ParsedMail, html_to_text, parse_message
from termpilot.settings import MailProvider, Settings

logger = logging.getLogger(__name__)


class MailboxRejected(NotAuthenticated):
    code = "mailbox_rejected"


@dataclass(frozen=True)
class Outgoing:
    to: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str
    body: str
    html: str | None = None


class MailTransport(Protocol):
    def verify(self, address: str, secret: str) -> None: ...

    def fetch(self, address: str, secret: str, folder: str, limit: int, unread_only: bool) -> list[ParsedMail]: ...

    def send(self, address: str, secret: str, message: Outgoing) -> str: ...


class ImapSmtpTransport:
    def __init__(self, settings: Settings, provider: MailProvider) -> None:
        self.provider = provider
        self.timeout = settings.mail_timeout_seconds

    def _imap(self, address: str, secret: str) -> imaplib.IMAP4_SSL:
        try:
            client = imaplib.IMAP4_SSL(self.provider.imap_host, self.provider.imap_port, timeout=self.timeout)
        except OSError as exc:
            raise UpstreamFailure("The mail server could not be reached.") from exc
        try:
            client.login(address, secret)
        except imaplib.IMAP4.error as exc:
            client.logout()
            raise MailboxRejected("The mailbox rejected this address or authorization code.") from exc
        return client

    def verify(self, address: str, secret: str) -> None:
        self._imap(address, secret).logout()
        with self._smtp(address, secret):
            pass

    def fetch(self, address: str, secret: str, folder: str, limit: int, unread_only: bool) -> list[ParsedMail]:
        client = self._imap(address, secret)
        try:
            status, _ = client.select(f'"{folder}"', readonly=True)
            if status != "OK":
                raise InvalidInput(f"The folder {folder} does not exist.")
            status, found = client.uid("SEARCH", None, "UNSEEN" if unread_only else "ALL")  # type: ignore[arg-type]
            if status != "OK":
                raise UpstreamFailure("The mailbox search failed.")
            uids = (found[0] or b"").split()[-limit:]
            messages = []
            for uid in reversed(uids):
                status, parts = client.uid("FETCH", uid, "(BODY.PEEK[] FLAGS)")
                if status != "OK" or not parts:
                    continue
                # Servers may put FLAGS before or after the message literal.
                meta, raw = "", b""
                for part in parts:
                    if isinstance(part, tuple):
                        meta += part[0].decode(errors="ignore") if isinstance(part[0], bytes) else ""
                        raw = part[1] or raw
                    elif isinstance(part, bytes):
                        meta += part.decode(errors="ignore")
                if raw:
                    messages.append(parse_message(uid.decode(), raw, meta))
            return messages
        except (imaplib.IMAP4.error, OSError) as exc:
            raise UpstreamFailure("The mailbox could not be read.") from exc
        finally:
            try:
                client.logout()
            except (imaplib.IMAP4.error, OSError):
                pass

    def _smtp(self, address: str, secret: str) -> smtplib.SMTP_SSL:
        try:
            client = smtplib.SMTP_SSL(
                self.provider.smtp_host,
                self.provider.smtp_port,
                timeout=self.timeout,
                context=ssl.create_default_context(),
            )
        except OSError as exc:
            raise UpstreamFailure("The outgoing mail server could not be reached.") from exc
        try:
            client.login(address, secret)
        except smtplib.SMTPAuthenticationError as exc:
            client.close()
            raise MailboxRejected("The outgoing mail server rejected the authorization code.") from exc
        return client

    def send(self, address: str, secret: str, message: Outgoing) -> str:
        email = EmailMessage()
        message_id = make_msgid(domain=address.rsplit("@", 1)[-1])
        email["From"] = address
        email["To"] = ", ".join(message.to)
        if message.cc:
            email["Cc"] = ", ".join(message.cc)
        email["Subject"] = message.subject
        email["Date"] = formatdate(localtime=True)
        email["Message-ID"] = message_id
        email.set_content(message.body or html_to_text(message.html or "") or " ")
        if message.html:
            email.add_alternative(message.html, subtype="html")
        try:
            with self._smtp(address, secret) as client:
                client.send_message(email, from_addr=address, to_addrs=message.to + message.cc + message.bcc)
        except smtplib.SMTPRecipientsRefused as exc:
            raise InvalidInput("The mail server refused one of the recipients.") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise UpstreamFailure("The message could not be sent.") from exc
        return message_id


class DemoTransport:
    """Pretends to be a mailbox; sent messages are only logged."""

    SECRET = "demo"

    def verify(self, address: str, secret: str) -> None:
        if secret != self.SECRET:
            raise MailboxRejected("In demo mode the authorization code is: demo")

    def fetch(self, address: str, secret: str, folder: str, limit: int, unread_only: bool) -> list[ParsedMail]:
        now = utcnow()
        samples = [
            (
                "Office of Teaching Affairs <teaching@example.edu>",
                "Course drop deadline this Friday",
                "Reminder: the last day to drop a course without a W grade is this Friday at 17:00. "
                "Submit requests through the records system.",
                3,
                False,
            ),
            (
                "Dr. Lin Wei <linwei@example.edu>",
                "Problem Set 6 clarifications",
                "For question 3 you may assume the graph is connected. The submission deadline is unchanged: "
                "tomorrow 23:59 on the learning platform.",
                20,
                False,
            ),
            (
                "Library <library@example.edu>",
                "Your reserved book is ready",
                "The book 'Introduction to Algorithms' is ready for pickup at the main desk until next Tuesday.",
                50,
                True,
            ),
            (
                "Database Systems TA <db-ta@example.edu>",
                "Lab exam arrangements",
                "The lab exam takes place in Computer Lab 402 on Thursday afternoon. Bring your student card.",
                75,
                True,
            ),
        ]
        messages = []
        for index, (sender, subject, body, hours_ago, seen) in enumerate(samples):
            if unread_only and seen:
                continue
            messages.append(
                ParsedMail(
                    uid=str(1000 + index),
                    message_id=f"<demo-{index}@example.edu>",
                    subject=subject,
                    sender=sender,
                    recipients=address,
                    cc=None,
                    received_at=now - timedelta(hours=hours_ago),
                    preview=body[:180],
                    body_text=body,
                    body_html=None,
                    seen=seen,
                    has_attachments=False,
                )
            )
        return messages[:limit]

    def send(self, address: str, secret: str, message: Outgoing) -> str:
        logger.info("Demo mode: pretending to send %r to %s", message.subject, ", ".join(message.to))
        return f"<demo-{int(utcnow().timestamp())}@example.edu>"


def build_transport(settings: Settings, provider: str) -> MailTransport:
    if settings.demo_mode:
        return DemoTransport()
    config = settings.mail_providers.get(provider)
    if config is None:
        raise InvalidInput(f"Unsupported mail provider: {provider}.")
    return ImapSmtpTransport(settings, config)
