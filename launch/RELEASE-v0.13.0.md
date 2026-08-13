# SAM Doctor v0.13.0

This release makes the first run easier to trust and the awkward failure paths
harder to lose evidence in.

The website can now diagnose a pasted deployment log locally with the same
generated 91-rule catalog used by the CLI. Nothing is uploaded, and the
credential-free sample states the one result a new user should expect before
they try their own log.

The catalog adds a focused API Gateway deployment-throttling diagnosis for
control-plane `TooManyRequestsException` and CloudFormation 429 failures. It
does not mistake an application's ordinary HTTP 429 response for a deployment
failure.

The release also fixes several quiet edge cases: multiline deploy commands in
generated workflows, truly recursive batch globs, UTF-16/32 input on stdin and
in the Action, quoted multi-word secret redaction, overlapping batch inputs,
and report or log outputs that point through symbolic links. A failed command
launch now preserves the previous deployment log instead of truncating it.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Action with `jakegold1647/sam-doctor@v0`.
- Run `sam-doctor demo` for the no-credentials first check.
- Reports remain local and redacted. Review any report before sharing it.
