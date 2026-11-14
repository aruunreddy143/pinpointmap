"""Outgoing SMS and email. A small interface so real providers (chosen later: India SMS rules,
email service) plug in without touching the auth code. Tests use the outbox."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

log = logging.getLogger("pinpoint.notify")


@dataclass(frozen=True)
class Message:
    channel: Literal["sms", "email"]
    to: str
    subject: str
    body: str


class Notifier(Protocol):
    def send(self, message: Message) -> None: ...


class OutboxNotifier:
    """Keeps messages in memory. Used in tests. Never use in production."""

    def __init__(self) -> None:
        self.sent: list[Message] = []

    def send(self, message: Message) -> None:
        self.sent.append(message)


class ConsoleNotifier:
    """Development only: prints messages to the server log so sign-in can be tried by hand."""

    def send(self, message: Message) -> None:
        log.warning(
            "DEV message to %s (%s): %s | %s", message.to, message.channel, message.subject, message.body
        )


class UnconfiguredNotifier:
    """Production default until an SMS/email provider is configured: fail loudly, never silently drop."""

    def send(self, message: Message) -> None:
        raise RuntimeError("No SMS/email provider is configured (PINPOINT_ENVIRONMENT=production)")
