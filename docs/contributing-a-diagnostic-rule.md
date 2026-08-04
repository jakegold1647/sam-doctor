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
8. Add the rule to the supported-category documentation when appropriate.

## Local workflow

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

The core rule catalog lives in `src/sam_doctor/diagnostics.py`. The main
regression cases are in `tests/test_diagnostics.py`. A focused contribution
usually changes one rule, its positive and negative tests, and a short changelog
entry.

## Safe fixture example

```text
MyFunction CREATE_FAILED
Lambda does not have permission to access the ECR image.
```

Do not include account IDs, ARNs, email addresses, tokens, customer data, or a
complete production log. Review every excerpt manually before submitting it.

## Worked example (minimal end-to-end)

When your branch adds one new pattern, touch only one rule block and one test pair:

### 1) Add the rule to `src/sam_doctor/diagnostics.py`

```python
Rule(
    id="SAM-NEW-0001",
    title="S3 artifact bucket permission is not configured",
    confidence="medium",
    patterns=(
        r"Access\\s+Denied|AccessDenied|not\\s+authorized\\s+to\\s+s3",
    ),
    evidence_label="Bucket access",
    evidence="S3 artifact access appears blocked in the deployment output.",
    verify=(
        "Confirm the artifact bucket and object key permissions for the build role.",
        "Verify the deploy IAM policy still allows `s3:GetObject` and `s3:PutObject` as needed.",
    ),
    docs_url="https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-bucket-policies.html",
),
```

Use one stable title, one confidence, 2–4 verify steps, and one official link.

### 2) Add focused positive/negative tests in `tests/test_diagnostics.py`

```python
def test_detects_bucket_access_block() -> None:
    findings = diagnose("AccessDenied: User is not authorized to perform s3:PutObject")
    assert len(findings) == 1
    assert findings[0].id == "SAM-NEW-0001"
    assert findings[0].title == "S3 artifact bucket permission is not configured"

def test_does_not_match_unrelated_s3_output() -> None:
    findings = diagnose("Created artifact bucket with standard permissions.")
    assert findings == []
```

If the pattern is multi-line, use a strict fixture with both supporting and
exclusion lines so false positives are covered.

### 3) Run and commit a focused PR

```bash
python -m pytest -q \
  tests/test_diagnostics.py::test_detects_bucket_access_block \
  tests/test_diagnostics.py::test_does_not_match_unrelated_s3_output
```

If the rule is accepted, keep the fixture text short, add a short changelog entry,
and update the matching docs page where practical.
