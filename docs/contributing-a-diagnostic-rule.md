# Contributing a diagnostic rule

A diagnostic rule should turn one explicit, recurring failure signal into a
focused next step. Keep the rule deterministic and bounded: SAM Doctor does not
inspect an AWS account or claim an authoritative root cause.

## Rule checklist

1. Start with the smallest sanitized log line that demonstrates the failure.
2. Add a nearby non-match so the rule does not trigger on a successful or
   unrelated line.
3. Give the rule a specific title and confidence level.
4. Explain what the evidence supports and what it does not prove.
5. Add safe verification steps that help a developer confirm the diagnosis.
6. Link the relevant official AWS, GitHub, or service documentation.
7. Add redaction coverage if the evidence can contain identifiers.
8. If the rule overlaps an existing one, choose `suppressed_by` or
   `excluded_line_patterns` deliberately - see
   [the note below](#choosing-between-suppressed_by-and-excluded_line_patterns)
   - and check that an unrelated failure in the same log still reports.
9. Give the rule a stable `id`, a `RULE_FIXTURES` entry in
   `scripts/check-rule-fixtures.py`, and an error page under `site/errors/`
   with its `ERROR_PAGE_MAP` entry and index link. All three are enforced: the
   gates fail on a rule that is missing any of them.
10. Add a short changelog entry and include this PR in the next release if the
    rule is accepted.

## What is already normalized before your patterns run

Write patterns against the log as a person reads it. `diagnose()` strips terminal
escape sequences first, so a pattern never has to tolerate a colour code sitting
inside a word — do not write `FAIL(?:\x1b\[[0-9;]*m)?ED`.

Nothing else is normalized, and nothing else needs to be: patterns are searched
*within* a line, so a timestamp prefix, a CI log prefix, leading indentation, or a
progress-bar carriage return ahead of your text cannot stop a match. CRLF and
trailing whitespace are harmless for the same reason.

Two consequences worth knowing:

- Do not anchor with `^` unless you truly mean a line with nothing before your
  text. Real deployment logs almost always have something before it.
- `suppressed_by` is searched against the whole log rather than one line, which is
  why it is the wrong tool when two rules describe the same line — see
  [the note below](#choosing-between-suppressed_by-and-excluded_line_patterns).

## Local workflow

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

The core rule catalog lives in `src/sam_doctor/diagnostics.py`. The main
regression cases are in `tests/test_diagnostics.py`. A focused contribution usually
changes one rule, its positive and negative tests, and a short changelog entry.

## Safe fixture example

```text
MyFunction CREATE_FAILED
Lambda does not have permission to access the ECR image.
```

Do not include account IDs, ARNs, emails, tokens, customer data, or full
production logs. Review every excerpt manually before submitting it.

## Worked example (minimal end-to-end)

When your branch adds one new pattern, touch only one rule block and one test pair:

### 1) Add the rule to `src/sam_doctor/diagnostics.py`

```python
Rule(
    title="CloudFormation resource access to artifact bucket is blocked",
    confidence="medium",
    patterns=(
        r"access denied\\s*.*GetObject.*artifact-bucket",
        r"Could not read object from S3:.*AccessDenied",
    ),
    explanation=(
        "SAM could not read or write a build artifact from S3 during deployment. "
        "A review of the role and bucket policy is needed before retrying."
    ),
    verification=(
        "Confirm the deployment role has the required artifact bucket permissions for this path.",
        "Check the bucket policy and KMS policy for the same role and artifact key.",
        "Verify the deploy IAM policy still allows `s3:GetObject` and `s3:PutObject` as needed.",
    ),
    documentation_url="https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html",
    suppressed_by=(),
    excluded_line_patterns=(),
),
```

Use one stable title, one confidence value, two to four verification steps, and
one official link.

#### Choosing between `suppressed_by` and `excluded_line_patterns`

Both keep two rules from reporting the same failure twice, and picking the
wrong one is the most common thing that comes back in review. The question to
ask is whether the other rule is describing **the same event** or **a different
event that happens to appear in the same log**.

- **`suppressed_by`** turns your rule off for the *entire log* when the pattern
  appears anywhere in it. Use it when the other rule explains the same event
  more precisely: a `CREATE_FAILED` whose status reason is a taken bucket name
  is one failure, and only the bucket rule should speak.
- **`excluded_line_patterns`** skips just the *matching lines* and lets your
  rule keep reporting everything else. Use it when both failures can genuinely
  co-occur and each deserves its own finding.

Getting this backwards hides real failures. A nested-stack rule that suppressed
the generic resource rule for the whole log meant a parent stack failing a child
*and* an unrelated queue reported only the nested finding - the queue failure
disappeared. Per-line exclusion fixed it, because those are two different
events. The denial rules use the same approach for the same reason.

A quick way to check: write a fixture that puts your failure and an unrelated
one in the same log, and confirm both still report.

### 2) Add focused positive/negative tests in `tests/test_diagnostics.py`

```python
def test_detects_artifact_bucket_access_block() -> None:
    findings = diagnose("Could not read object from S3: AccessDenied for my-artifact-bucket/packaged.yaml")
    assert len(findings) == 1
    assert findings[0].title == "CloudFormation resource access to artifact bucket is blocked"

def test_does_not_match_unrelated_s3_output() -> None:
    findings = diagnose("Created artifact bucket with standard permissions and retried successfully.")
    assert findings == []
```

If the pattern is multi-line, include adjacent non-matches in the positive fixture
to reduce false positives.

### 3) Run and commit a focused PR

```bash
python scripts/check-rule-catalog.py
python -m pytest -q \
  tests/test_diagnostics.py::test_detects_artifact_bucket_access_block \
  tests/test_diagnostics.py::test_does_not_match_unrelated_s3_output
```

`check-rule-catalog.py` is the same objective gate CI runs: it verifies every
pattern compiles, that none can fire on ordinary successful deploy output, and
that the rule's metadata (title, confidence, verification steps, documentation
link) is complete. Run it first — it reports every structural problem at once.

If the rule's family already has entries in `scripts/check-rule-fixtures.py`
(`RULE_FIXTURES`), add this rule's title alongside them so the registry stays
complete for that family:

```bash
python scripts/check-rule-fixtures.py --rule "part of the new rule's title"
```

If the rule is accepted, keep the fixture text short, add a short changelog entry,
and update the matching docs page where practical.
