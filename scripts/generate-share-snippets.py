#!/usr/bin/env python3
"""Generate copy-ready SAM Doctor outreach snippets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnippetTemplate:
    audience: str
    headline: str
    body: str
    command: str


ERROR_TEMPLATES = {
    "oidc": SnippetTemplate(
        audience="engineers / SREs",
        headline="OIDC / AssumeRoleWithWebIdentity in deployment logs",
        body=(
            "I found a deployment OIDC trust-mismatch signal and a focused next check."
        ),
        command="sam-doctor diagnose deployment.log --format markdown",
    ),
    "rollback": SnippetTemplate(
        audience="on-call responders",
        headline="CloudFormation rollback noise",
        body=(
            "I isolated the first actionable failure before the rollback noise in logs."
        ),
        command="sam-doctor diagnose deployment.log --format markdown",
    ),
    "capability": SnippetTemplate(
        audience="platform and IAM teams",
        headline="CAPABILITY_IAM rollout blocker",
        body="I found the first IAM capability acknowledgement requirement and validation step.",
        command="sam-doctor diagnose deployment.log --format markdown",
    ),
    "ecr": SnippetTemplate(
        audience="build and release engineers",
        headline="ECR image-access failure in CI",
        body="I found a deploy-path image access failure and the minimum safe follow-up.",
        command="sam-doctor diagnose deployment.log --format markdown",
    ),
    "build": SnippetTemplate(
        audience="release engineers",
        headline="SAM/CDK build failure",
        body="I found the first actionable failure in a noisy build/deploy excerpt.",
        command="sam-doctor diagnose deployment.log --format markdown",
    ),
}


CHANNEL_PREFIX = {
    "chat": "I used this in incident/Slack/Teams text:",
    "discord": "I posted this in Discord:",
    "email": "I sent this update:",
    "hn": "For a public discussion thread:",
    "reddit": "For Reddit:",
    "x": "For X / Twitter:",
}


BASE_URL = "https://sam-doctor.jacobgoldstein.dev/"


def _snippet_link(error: str, utm_medium: str) -> str:
    anchor = "#proof-title" if error in {"ecr", "build", "rollback"} else ""
    base = BASE_URL.rstrip("/")
    if anchor:
        return (
            f"{base}/{anchor}"
            f"?utm_source=share_script&utm_medium={utm_medium}"
        )
    return (
        f"{BASE_URL}?"
        f"utm_source=share_script&utm_medium={utm_medium}"
    )


def generate_snippet(
    *, error: str, channel: str, include_link: bool, include_command: bool, utm_medium: str
) -> str:
    template = ERROR_TEMPLATES[error]
    lines = [
        CHANNEL_PREFIX[channel],
        f"{template.headline} for {template.audience}.",
        template.body,
    ]
    lines.append(template.command if include_command else "Top finding + safe verification check.")
    if include_link:
        lines.append(_snippet_link(error, utm_medium))
    return "\n".join(lines).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate SAM Doctor outreach snippets.")
    parser.add_argument(
        "--error",
        choices=sorted(ERROR_TEMPLATES.keys()),
        default="oidc",
        help="Failure family to target.",
    )
    parser.add_argument(
        "--channel",
        choices=sorted(CHANNEL_PREFIX.keys()),
        default="chat",
        help="Where the snippet will be shared.",
    )
    parser.add_argument(
        "--utm-medium",
        default="shared",
        help="UTM medium appended to tracking links.",
    )
    parser.add_argument(
        "--no-link",
        action="store_true",
        help="Generate without a link.",
    )
    parser.add_argument(
        "--no-command",
        action="store_true",
        help="Skip showing the command in the snippet.",
    )
    parser.add_argument(
        "--out",
        help="Optional path to write snippet output.",
    )
    args = parser.parse_args(argv)

    snippet = generate_snippet(
        error=args.error,
        channel=args.channel,
        include_link=not args.no_link,
        include_command=not args.no_command,
        utm_medium=args.utm_medium,
    )
    if args.out:
        Path(args.out).write_text(snippet + "\n", encoding="utf-8")

    print(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
