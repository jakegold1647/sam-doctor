"""Redact common identifiers before evidence is displayed or written."""

from __future__ import annotations

import re


_ACCOUNT_ID = re.compile(r"(?<!\d)\d{12}(?!\d)")
_ARN = re.compile(r"arn:aws(?:-us-gov|-cn)?:[^\s'\"`]+")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_AWS_ACCESS_KEY_ID = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(aws_secret_access_key|aws_session_token|github_token|access_token|api_key|password|secret|token)\s*[:=]\s*[^\s'\"`]+"
)


def redact(text: str) -> str:
    """Return text with common cloud identifiers removed.

    The function intentionally makes no network calls. It does not claim to
    detect every possible secret, so users should still review reports before
    sharing them outside their team.
    """

    text = _ARN.sub("[REDACTED_ARN]", text)
    text = _ACCOUNT_ID.sub("[REDACTED_ACCOUNT_ID]", text)
    text = _AWS_ACCESS_KEY_ID.sub("[REDACTED_AWS_ACCESS_KEY]", text)
    text = _GITHUB_TOKEN.sub("[REDACTED_GITHUB_TOKEN]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED_SECRET]", text)
    return _EMAIL.sub("[REDACTED_EMAIL]", text)

