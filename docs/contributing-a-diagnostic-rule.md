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