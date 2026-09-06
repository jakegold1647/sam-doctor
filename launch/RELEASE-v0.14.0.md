# SAM Doctor v0.14.0

This release ships the five diagnostics that had been waiting on main since
v0.13.0, so the PyPI package and the public guides now cover the same 96
rules.

Four of the new rules cover hard AWS limits that read like generic failures: a
Lambda function whose layers push the unzipped total past 250 MB, EC2 user
data past 16 KB, an IAM role that hits its managed-policy attachment quota,
and one that exceeds the inline-policy aggregate size. The fifth separates a
CloudFormation create that collides with an existing stack name from the
rollback noise around it and starts with read-only stack checks rather than
deletion. The managed-policy quota rule was contributed by Sean.

`sam-doctor rules` gained `--search` and `--confidence` filters, so a long
catalog can be narrowed in the terminal or in JSON output without changing
what the matcher does.

Two redaction fixes make shared reports safer. A private home-directory path
is now removed in full instead of leaking its tail after the first `s`, and
packets, rule-request excerpts, and diagnostic Markdown strip Windows, macOS,
and Linux home paths inside matched evidence while keeping relative project
paths and the finding itself.

The website has a not-found page of its own, so a stale or mistyped link lands
on the searchable error index instead of a bare GitHub 404.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Action with `jakegold1647/sam-doctor@v0`.
- Run `sam-doctor demo` for the no-credentials first check.
- Reports remain local and redacted. Review any report before sharing it.
