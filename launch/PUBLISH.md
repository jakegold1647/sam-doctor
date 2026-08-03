# Publish a SAM Doctor release

This repository is already public. Use this checklist for a release you intend
to share with real users. Do not publish logs, customer failures, AWS
credentials, access keys, session tokens, or personal information.

## 1. Release preflight

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
python -m sam_doctor.cli demo
```

Confirm that the version in `pyproject.toml`, `src/sam_doctor/__init__.py`,
`CHANGELOG.md`, and the release note all agree.

For a quick machine-check before tag push, run:

```powershell
python scripts/check-launch.py --skip-outreach
python scripts/check-launch.py --skip-distribution \
  --outreach-log launch/outreach-log-template.csv \
  --outreach-summary artifacts/outreach-summary.md \
  --strict-ethical --min-feedback-ratio 100
python scripts/check-launch.py \
  --strict-distribution-during-release \
  --strict-ethical --min-feedback-ratio 100 \
  --allow-no-data-in-strict \
  --outreach-log launch/outreach-log-template.csv \
  --outreach-summary artifacts/outreach-summary.md
```

## 2. Publish the public tool

1. Open the repository's Actions tab and confirm the `Verify free core` workflow passes.
2. Push the matching `vX.Y.Z` tag. The `Publish release` workflow builds the
   wheel and source archive. It creates a regular release for plain semantic
   version tags (such as `v0.7.4`) and a prerelease for pre-release tag names
   (such as `v0.7.4-rc.1`) using `launch/RELEASE-${TAG}.md` when present.
3. Verify the release is published and not a pre-release before final
   Marketplace publishing. A draft or pre-release can cause Marketplace and GitHub
   to surface misleading "Latest pre-release" metadata.
4. Confirm GitHub Pages serves the current `site/` directory.
5. In repository Settings, set the homepage to the GitHub Pages URL and add these
   topics: `aws`, `aws-sam`, `cloudformation`, `github-actions`, `iam`,
   `serverless`, `python`, `cli`.
6. Upload `site/assets/sam-doctor-social-preview.jpg` as the repository's social
   preview image.
7. If this tag includes a pre-release suffix, convert to full release only after
   internal sign-off. For plain `vX.Y.Z` releases, Marketplace and PyPI publish
   flows can use the release as soon as release notes and checks are green.

After the first release, re-run the preflight with
`--strict-distribution-during-release` to ensure PyPI, Pages, and Marketplace are
live in addition to ethical-growth quality checks.

For the GitHub Action listing, follow `launch/MARKETPLACE.md` after the
repository owner has reviewed and accepted GitHub's Marketplace Developer
Agreement.

If you want the distributed health snapshot to fail on hard launch-channel
readiness after publish, trigger `distribution-check.yml` manually with
`strict-distribution-during-release: true`.

## 3. Prepare a founder checkout only after validation

Create a Lemon Squeezy one-time product using `launch/PRODUCT-LISTING.md`.

Do not activate a purchase button until the product description includes the
delivery condition and refund terms. If you add a checkout link, place it in
`site/index.html` only after the terms are visible.

## 4. First distribution

Use `launch/LAUNCH-PLAN.md` and `launch/OUTREACH.md` for personalized conversations with developers who have a recent, public SAM, CloudFormation, IAM, or GitHub Actions error. Lead with the free tool and ask for a sanitized failure. Ask for founder payment only after the report proves useful.

Use `python scripts/check-distribution.py` periodically (or before major outreach bursts)
to confirm star growth, GitHub activity, and channel visibility remain on track.

## Definition of the first revenue milestone

Three $39 founder purchases from people who are not friends or family. Record the buyer type, problem, acquisition channel, and feedback without storing their logs or credentials.

Use `--outreach-log` to point to your tracked outreach file:

```powershell
python scripts/check-launch.py --skip-distribution --outreach-log launch/outreach-log-template.csv --outreach-summary artifacts/outreach-summary.md
```
