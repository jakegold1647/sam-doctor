# Contributing to SAM Doctor

The most useful contributions are reproducible false positives, missed failure
patterns, and improvements to safe verification steps.

You do not need to write code to help. If SAM Doctor helped, missed a failure,
or left you unsure what to do next, share a sanitized result through the
[usage feedback form](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml).
Those reports give maintainers the context to improve a fixture, rule, or guide,
and you can ask for help turning one into your first pull request.

Maintainers use the [community triage checklist](docs/community-triage.md) to
route that feedback into a focused, welcoming next step.

The [community outreach plan](docs/community-outreach-plan.md) describes the
help-first usage and contribution loop. It is intentionally conversation-first:
no mass messages, star exchanges, or pressure to join another platform.

Please read the [Code of Conduct](CODE_OF_CONDUCT.md) before opening an issue,
discussion, or pull request. It sets the project standard for respectful
feedback and keeps the privacy boundary clear for everyone, including first-
time contributors.

## Before opening an issue

Never post raw production logs, AWS account IDs, ARNs, access keys, session
tokens, customer data, or private repository names. Redaction helps with common
identifiers, but it is not a substitute for reviewing an excerpt yourself.

For a diagnostic problem, include:

1. The SAM Doctor version from `sam-doctor --version`.
2. The exact command you ran, with private paths or values replaced.
3. A short, sanitized excerpt containing the first relevant error.
4. What you expected the report to say and what it said instead.

For tooling improvements, use the feature request template and include:

1. the command or workflow family,
2. the behavior gap.

## First contribution path

If this is your first contribution, choose the smallest path that fits:

1. **Docs or community:** pick a `good first issue`, correct a guide, or share a
   safe result through the [usage feedback form](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml),
   [Ideas](https://github.com/jakegold1647/sam-doctor/discussions/categories/ideas),
   or [Show and tell](https://github.com/jakegold1647/sam-doctor/discussions/categories/show-and-tell).
   No code is required.
2. **Diagnostic or fixture:** claim a scoped rule issue and follow the
   [diagnostic-rule guide](docs/contributing-a-diagnostic-rule.md). Add one
   positive case and one nearby non-match when behavior changes.
3. **Any path:** keep the change narrow, run `python scripts/check-pr.py`, and
   open a PR using the template. Include the command, example, or documentation
   page that lets a reviewer reproduce what changed.

To lower contributor friction, labels to look for:

- `good first issue`
- `documentation`
- `help wanted`
- `status: ready`
- `mentor available`
- `effort: small` or `effort: medium`

The [ready newcomer queue](https://github.com/jakegold1647/sam-doctor/issues?q=is%3Aissue+is%3Aopen+label%3A%22status%3A+ready%22+label%3A%22mentor+available%22)
is the shortest route to a scoped first pull request. These issues have
acceptance criteria and a maintainer path for questions; leave a brief claim
comment before you start so nobody duplicates the work.

### What happens after you claim

1. Comment `I'd like to take this` on the issue and say what you plan to try.
2. A maintainer will confirm the scope, answer setup questions, and assign the
   issue or remove `status: ready` so nobody starts duplicate work.
3. Open a draft PR when you have a test, fixture, documentation sketch, or first
   working step. Link the issue and the exact command you ran; feedback before
   the change is finished is welcome.
4. Keep the change narrow and run the PR gate. Once the checks are green, we
   review the evidence and merge it with your credit preserved.

If you would like to be named publicly, add or correct your entry in
`CONTRIBUTORS.md` and run `python scripts/sync-contributor-page.py`. That keeps
the README callout and the website Hall of Fame in the same reviewed change.

If you want help before claiming an issue, ask in the [welcome discussion](https://github.com/jakegold1647/sam-doctor/discussions/1)
or use the [contributor setup form](https://github.com/jakegold1647/sam-doctor/issues/new?template=setup_problem.yml).

Want a ready-made first PR? The [rule roadmap](docs/rule-roadmap.md) lists
fully specified diagnostic rules waiting for a contributor — each with sample
log lines, pattern hints, non-match cases, and verification steps already
drafted, so the PR is mostly a translation exercise.

Two of those are **reserved for first-time contributors**:
[#21](https://github.com/jakegold1647/sam-doctor/issues/21) (IAM policy size and
attachment quotas) and
[#25](https://github.com/jakegold1647/sam-doctor/issues/25) (API Gateway
`TooManyRequestsException`). If this is your first PR here, either is yours for
the asking. If it is not, please leave them. That reservation is repeated here and
at the top of the roadmap because it used to appear only in a paragraph halfway
down the roadmap, below the specs themselves - easy to read the spec and miss the
request.

For rule proposals, use `docs/contributing-a-diagnostic-rule.md` and keep the
change scope to one signal and one fixture pair.

## If you get stuck

Open a draft PR as soon as you have a failing test, partial fixture, or
documentation sketch. In the description, link the issue, include the command
you ran, and name the exact question; a maintainer can review the direction
before the change is finished. Draft PRs are welcome, and you do not need to
solve the remaining problem before asking for help.

## Development setup

SAM Doctor supports Python 3.10 through 3.13 on Linux, macOS, and Windows.
CI enforces this: the test suite and quality gates run on Ubuntu (all four
Python versions) and on Windows, and the composite Action is exercised on
both. One caveat for Windows contributors: the action-wrapper tests run the
bash wrapper script through a WSL-style bash and skip themselves when only
Git Bash is available - the Windows CI job covers the Action itself directly,
so a skip there is expected, not a failure to fix.

The pull-request gate is fork-safe: it runs on public fixtures through
`pull_request` and does not require AWS credentials, repository secrets, or
write access. A first-time contributor can open a fork PR and let the same
checks run before asking for maintainer help.

### Fork, clone, and branch

1. Fork the repository on GitHub.
2. Clone your fork and add the upstream remote:

   ```bash
   git clone https://github.com/YOUR-USER/sam-doctor.git
   cd sam-doctor
   git remote add upstream https://github.com/jakegold1647/sam-doctor.git
   ```

3. Create a branch: `git switch -c fix/short-description`

### Branch lanes

`staging` is the shared testing ground for maintainer integration work. It runs
the same verification and commit-metadata checks as `main`, but it never
publishes the website or a release. Maintainers may combine reviewed community
changes there, run the full gate, and promote the green result to `main` with a
reviewed pull request.

Keep working in a focused feature branch and send normal contributor pull
requests for review. Do not push directly to `main`; use `staging` only when a
maintainer asks for an integration test or when you are explicitly maintaining
the shared pre-release lane.

### Create an isolated environment

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then install the project with development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Verify the baseline before editing

```bash
python scripts/check-pr.py
```

This one command runs everything CI requires on a pull request: site
metadata, site QA, Ruff, the rule-catalog gate, the test suite, the package
build, and the onboarding smoke check. `--fast` skips the build and smoke
steps during iteration. The individual commands, if you prefer them:

```bash
python -m ruff check src tests scripts
python -m pytest -q
python -m build
python scripts/run-smoke.py
```

If the baseline fails before you have changed anything, open an issue with
the [contributor setup problem](https://github.com/jakegold1647/sam-doctor/issues/new?template=setup_problem.yml)
form instead of debugging alone.

### Focused diagnostic-rule tests

```bash
python -m pytest tests/test_diagnostics.py -q
python scripts/check-rule-catalog.py
```

Keep rules deterministic, explain the evidence they match, and add regression
coverage for both the intended failure and a nearby non-failure case. Do not add
commands that change AWS resources or require credentials.

### Pattern safety

`scripts/check-rule-catalog.py` also times every pattern against adversarial
input. sam-doctor reads log text it does not control, so a pattern that
backtracks catastrophically (nested quantifiers like `(a+)+b`, or `.*` where
`.{0,80}` would do) could hang a real CI job. The check fails such a pattern
with the bounded form to use instead.

### Documentation links

Every rule points a user at official documentation, and those URLs rot as AWS
reorganizes its docs. `scripts/check-doc-links.py` verifies them, and a
scheduled workflow runs it weekly.

It is deliberately not part of `check-pr.py`: sam-doctor runs offline, and a
network call in the PR gate would make your build depend on someone else's
website being reachable. If the scheduled run fails, update the link on the
rule and on its error page in the same PR.

```bash
python scripts/check-doc-links.py
```

### Rule fixture registry

`scripts/check-rule-fixtures.py` tracks a positive and nearby-negative fixture
per stable rule id, separately from the regression tests above, so the fixture
set a rule needs is visible without reading `tests/test_diagnostics.py`. The
registry covers the whole catalog, and the check fails when a catalog rule has
no entry - so a new rule needs its `RULE_FIXTURES` entry in the same PR.

```bash
python scripts/check-rule-fixtures.py                     # whole registry
python scripts/check-rule-fixtures.py --rule oidc         # one rule family
```

### Website error-page mapping

`site/errors/` and the rule catalog are maintained separately, so
`scripts/check-error-pages.py` keeps them from drifting apart: `ERROR_PAGE_MAP`
lists every rule with a dedicated page, and the check fails on a mapping that
points at a renamed or removed rule, a page that no longer exists, two rules
sharing a page, a page that exists (or is linked from `site/errors/index.html`)
without an entry, or a page whose stated confidence no longer matches its rule.

```bash
python scripts/check-error-pages.py
```

Coverage is complete, and the check keeps it that way: **a new rule needs a
page** under `site/errors/`, an `ERROR_PAGE_MAP` entry, and a link from
`site/errors/index.html`, all in the same PR. Copy the closest existing page
for the structure - what the error means, the fix in the order people actually
try things, and read-only verification commands.

## Pull requests

Use the repository PR template and keep a change narrow enough to review safely.
For new diagnostics, follow [Contributing a diagnostic rule](docs/contributing-a-diagnostic-rule.md)
and include both a positive fixture and a nearby non-match. Maintainers may ask
for a smaller excerpt or clearer evidence before merging.
