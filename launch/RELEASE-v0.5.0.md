# SAM Doctor v0.5.0

SAM Doctor v0.5.0 adds a direct diagnosis for a common CloudFormation change-set
failure that otherwise gets lost in generic deployment output.

## Highlights

- Detects `InsufficientCapabilities` and required `CAPABILITY_*` errors with a
  high-confidence, capability-specific report.
- Explains the distinction between IAM, named-IAM, and nested-application
  acknowledgements without recommending a broader permission than the error needs.
- Adds a bundled `sam-doctor demo --scenario capabilities` example.

SAM Doctor runs locally and provides verification steps only. Review the
template, generated change set, and permission impact before acknowledging a
CloudFormation capability.
