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
# `Basic` was missing while `Bearer` was handled, and it is the more decodable of
# the two: the value is base64 of `user:password`, so it hands over a reusable
# credential rather than a token that may expire. Docker, npm and pip registry
# auth all print this shape, and so does any curl run with -v.
_BASIC_AUTH = re.compile(r"(?i)\b(authorization\s*:\s*basic)\s+[A-Za-z0-9+/=]{8,}")
# An incoming webhook URL is a credential in link form: whoever holds it can post
# as the integration, and there is nothing else to authenticate. Deploy
# notification steps print them when the post itself fails, which is exactly the
# log someone attaches to a bug report.
_WEBHOOK_URL = re.compile(
    r"(?i)\bhttps://(?:hooks\.slack\.com/(?:services|workflows)/[A-Za-z0-9/_-]{8,}"
    r"|discord(?:app)?\.com/api/webhooks/[0-9]{5,}/[A-Za-z0-9._-]{8,}"
    r"|[a-z0-9-]+\.webhook\.office\.com/webhookb2/[A-Za-z0-9@/._-]{8,})"
)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
# A home-directory path can expose both the local user and a private checkout.
# Keep this intentionally narrow: absolute Windows paths below C:\Users and
# Unix/macOS paths below /home or /Users. Relative project paths remain useful
# evidence, and URL paths are not local filesystem evidence.
_PRIVATE_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9_:/])(?:[A-Z]:[\\/]+Users[\\/]+[^\\/\\s'"]+|"
    r"[\\/](?:Users|home)[\\/][^\\/\\s'"]+)(?:[\\/][^\\/\\s'"]+)*"
)

# Values that are configuration whatever key they sit under. `permissions: id-token:
# write` is a GitHub permission level, and it was being starred out of the evidence
# for the OIDC rule - deleting the single word a reader needs in order to fix the
# failure. No real secret is the literal string `write`.
_BENIGN_VALUES = ("write", "read", "none", "true", "false", "admin", "null")
_SECRET_ASSIGNMENT = re.compile(
    # Deliberately no leading \b. Environment variables are conventionally
    # UPPER_SNAKE_CASE with a prefix - DB_PASSWORD, APP_SECRET, MY_API_KEY - and
    # `_` is a word character, so \b never matched between the prefix and the
    # keyword. That left the most common real-world spelling of a secret
    # unredacted while the bare `password=` form was caught. The `[:=]` that
    # follows is what makes this specific, not the word boundary: a keyword
    # inside an unrelated word (`tokenizer=fast`) still fails to match because
    # the separator has to come directly after the keyword.
    r"(?i)(aws_secret_access_key|aws_session_token|github[_-]?token|access[_-]?token"
    r"|api[_-]?key|password|passwd|secret|token"
    # CamelCase JSON keys as printed by `aws sts assume-role` / `get-session-token`
    # output pasted into logs, plus common config spellings and the presigned-URL
    # signature parameter.
    r"|secret[_-]?access[_-]?key|session[_-]?token|client[_-]?secret|private[_-]?key"
    r"|x-amz-signature)"
    # The optional quote closes a quoted JSON/YAML key; the opening value quote
    # belongs to group 3 so the replacement can preserve a balanced pair.
    r"([\"'`]?\s*[:=]\s*)"
    # Quoted values may contain spaces and escaped quotes. Keep them on one line:
    # a missing closing quote must not consume the rest of a pasted deployment
    # log. The final branch retains the ordinary unquoted assignment shape.
    r"(?!\[REDACTED)(\"(?:\\.|[^\"\\\r\n])*\"?"
    r"|'(?:\\.|[^'\\\r\n])*'?"
    r"|`(?:\\.|[^`\\\r\n])*`?"
    r"|[^\s'\"`]+)"
)
# Credentials embedded in a URL: `https://user:token@host/path`, and the
# token-as-username form `https://glpat-xxx@host/path`. Both are ordinary in CI
# (`git clone https://oauth2:$TOKEN@host/repo`). These were previously redacted
# only by accident, when the email pattern happened to match `password@host` -
# which requires a dot in the host, so an internal single-label host like
# `gitlab` or `localhost` leaked the credential in full, and when it did match
# the value was mislabelled as an email address.
_URL_CREDENTIALS = re.compile(
    r"(?i)\b([a-z][a-z0-9+.\-]{1,20}://)([^\s:/@]{1,200})(:[^\s/@]{1,400})?@"
)
# Slack tokens show up in CI logs through notification steps.
_SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
_DOCKER_HUB_TOKEN = re.compile(r"\bdckr_pat_[A-Za-z0-9_-]{16,}\b")
# A password passed on a login command line. This matters here more than it looks:
# `ecr.auth.login-failed` is a rule in this catalog, so a log containing a failed
# registry login is a log this tool is built to be handed - and `docker login -p
# <token>` puts a live registry credential in it.
#
# Anchored to a line containing `login` on purpose. A bare `-p` cannot be matched
# on its own: `mkdir -p /some/path` would have its path redacted, which mangles
# ordinary build output. `--password-stdin` is excluded because it is the *safe*
# idiom - it names no secret, and redacting it would hide the fact that the log
# shows someone doing the right thing.
_LOGIN_PASSWORD_FLAG = re.compile(
    r"(?i)(\blogin\b[^\n]{0,120}?)(--password(?!-stdin)|(?<=\s)-p)(\s+|=)(?!-)\S{6,}"
)
# The .netrc shape, which uses whitespace rather than `=` or `:` and so is invisible
# to the assignment pattern. Deliberately requires the `login <user>` prefix: a bare
# `password <word>` pattern redacts prose like "password is invalid".
_NETRC_PASSWORD = re.compile(r"(?i)\b(login\s+\S+\s+password)\s+\S+")
# `curl -u user:token`. The colon is required, so `-u AWS` alone is left alone.
_CURL_USERINFO = re.compile(r"(?i)(?<=\s)(-u|--user)(\s+|=)([^\s:]{1,120}):\S{4,}")
# PEM private-key material: redact from the BEGIN marker through the END
# marker, or to the end of the text when the block is truncated.
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?s:.*?)(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
)


def _redact_url_credentials(match: re.Match[str]) -> str:
    """Redact the credential half of a URL userinfo section.

    With a password present the username is usually a harmless placeholder
    (`oauth2`, `git`, `AWS`) and keeping it helps identify which credential
    failed, so only the password is replaced. With no password the single value
    *is* the credential - that is how a PAT is passed to `git clone` - so it is
    replaced instead.
    """

    scheme, user, password = match.group(1), match.group(2), match.group(3)
    if password:
        return f"{scheme}{user}:[REDACTED_URL_CREDENTIAL]@"
    return f"{scheme}[REDACTED_URL_CREDENTIAL]@"


def _redact_secret_assignment(match: re.Match[str]) -> str:
    """Redact one assignment while retaining its separator and value quotes."""

    raw_value = match.group(3)
    quote = raw_value[0] if raw_value[0] in "\"'`" else ""
    quote_is_closed = bool(quote and len(raw_value) >= 2 and raw_value[-1] == quote)
    value = raw_value[1:-1] if quote_is_closed else raw_value[len(quote) :]
    if value.casefold() in _BENIGN_VALUES:
        return match.group(0)
    closing_quote = quote if quote_is_closed else ""
    replacement = f"{quote}[REDACTED_SECRET]{closing_quote}"
    return f"{match.group(1)}{match.group(2)}{replacement}"


def redact(text: str) -> str:
    """Return text with common cloud identifiers removed.

    The function intentionally makes no network calls. It does not claim to
    detect every possible secret, so users should still review reports before
    sharing them outside their team.
    """

    # First, because a webhook URL is only recognizable while it is still intact.
    # A Discord webhook path starts with a numeric id, and the twelve-digit
    # account-id pass rewrites that id to a placeholder - after which this pattern
    # no longer matches and the token half of the URL, which is the actual secret,
    # survives into the report. Later passes may safely narrow what is left.
    text = _WEBHOOK_URL.sub("[REDACTED_WEBHOOK_URL]", text)
    # Also before the account-id pass, which would otherwise rewrite the registry
    # host in `docker login ... 123456789012.dkr.ecr...` and shorten the window
    # this pattern searches for the flag.
    text = _LOGIN_PASSWORD_FLAG.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}[REDACTED_PASSWORD]",
        text,
    )
    text = _NETRC_PASSWORD.sub(lambda match: f"{match.group(1)} [REDACTED_PASSWORD]", text)
    text = _CURL_USERINFO.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}:[REDACTED_PASSWORD]",
        text,
    )
    text = _DOCKER_HUB_TOKEN.sub("[REDACTED_DOCKER_TOKEN]", text)
    text = _ARN.sub("[REDACTED_ARN]", text)
    text = _ACCOUNT_ID.sub("[REDACTED_ACCOUNT_ID]", text)
    text = _AWS_ACCESS_KEY_ID.sub("[REDACTED_AWS_ACCESS_KEY]", text)
    text = _AWS_SESSION_TOKEN.sub("[REDACTED_AWS_SESSION_TOKEN]", text)
    text = _GITHUB_TOKEN.sub("[REDACTED_GITHUB_TOKEN]", text)
    text = _SLACK_TOKEN.sub("[REDACTED_SLACK_TOKEN]", text)
    text = _PRIVATE_KEY_BLOCK.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _BEARER_TOKEN.sub(lambda match: f"{match.group(1)} [REDACTED_BEARER_TOKEN]", text)
    text = _BASIC_AUTH.sub(lambda match: f"{match.group(1)} [REDACTED_BASIC_AUTH]", text)
    text = _SECRET_ASSIGNMENT.sub(_redact_secret_assignment, text)
    text = _JWT.sub("[REDACTED_JWT]", text)
    text = _PRIVATE_PATH.sub("[REDACTED_PRIVATE_PATH]", text)
    # Must run before the email pass: `user:password@host.tld` also matches the
    # email pattern, and letting that win both mislabels the credential and
    # leaves the dotless-host case unredacted.
    text = _URL_CREDENTIALS.sub(_redact_url_credentials, text)
    return _EMAIL.sub("[REDACTED_EMAIL]", text)

