# SAM Doctor v0.4.1

This patch release strengthens the local reporting guardrail for sensitive
deployment evidence.

## Highlights

- Redacts bearer-token values that appear after an `Authorization: Bearer` header
  or `Bearer` prefix.
- Redacts standalone JWT-shaped tokens, including GitHub Actions OIDC tokens,
  before matched evidence is printed or written to a report.

SAM Doctor still processes input locally and does not claim to be a complete
secret scanner. Review every report before sharing it outside your team.
