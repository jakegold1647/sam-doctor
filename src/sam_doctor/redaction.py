"""Redact common identifiers before evidence is displayed or written."""

from __future__ import annotations

import re

_ACCOUNT_ID = re.compile(r"(?<!\d)\d{12}(?!\d)")
_ARN = re.compile(r"arn:aws(?:-us-gov|-cn)?:[^\s'\"`]+")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_AWS_ACCESS_KEY_ID = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
# Bare temporary-credential session tokens as printed by STS output and debug
# logs: a long base64 run with the characteristic "IQoJ"/"FwoG" prefix.
_AWS_SESSION_TOKEN = re.compile(r"\b(?:IQoJ|FwoG)[A-Za-z0-9+/=]{50,}")
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_BEARER_TOKEN = re.compile(
    r"(?i)\b(authorization\s*:\s*bearer|bearer)\s+[A-Za-z0-9._~+/=-]{16,}"
)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(aws_secret_access_key|aws_session_token|github_token|access_token|api_key|password|secret|token"
    # CamelCase JSON keys as printed by `aws sts assume-role` / `get-session-token`
    # output pasted into logs, plus common config spellings and the presigned-URL
    # signature parameter.
    r"|secretaccesskey|sessiontoken|client[_-]?secret|private[_-]?key|x-amz-signature)"
    # Never consume a value another pattern already redacted - the session-token
    # marker must survive this later, broader pass.
    r"[\"'`]?\s*[:=]\s*[\"'`]?(?!\[REDACTED)[^\s'\"`]+[\"'`]?"
)
# Slack tokens show up in CI logs through notification steps.
_SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
# PEM private-key material: redact from the BEGIN marker through the END
# marker, or to the end of the text when the block is truncated.
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?s:.*?)(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
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
    text = _AWS_SESSION_TOKEN.sub("[REDACTED_AWS_SESSION_TOKEN]", text)
    text = _GITHUB_TOKEN.sub("[REDACTED_GITHUB_TOKEN]", text)
    text = _SLACK_TOKEN.sub("[REDACTED_SLACK_TOKEN]", text)
    text = _PRIVATE_KEY_BLOCK.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _BEARER_TOKEN.sub(lambda match: f"{match.group(1)} [REDACTED_BEARER_TOKEN]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED_SECRET]", text)
    text = _JWT.sub("[REDACTED_JWT]", text)
    return _EMAIL.sub("[REDACTED_EMAIL]", text)

