"""Redact common identifiers before evidence is displayed or written."""

from __future__ import annotations

import re


_ACCOUNT_ID = re.compile(r"(?<!\d)\d{12}(?!\d)")
_ARN = re.compile(r"arn:aws(?:-us-gov|-cn)?:[^\s'\"`]+")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def redact(text: str) -> str:
    """Return text with common cloud identifiers removed.

    The function intentionally makes no network calls. It does not claim to
    detect every possible secret, so users should still review reports before
    sharing them outside their team.
    """

    text = _ARN.sub("[REDACTED_ARN]", text)
    text = _ACCOUNT_ID.sub("[REDACTED_ACCOUNT_ID]", text)
    return _EMAIL.sub("[REDACTED_EMAIL]", text)

