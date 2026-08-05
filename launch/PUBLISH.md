# Publish a SAM Doctor release

This repository is already public. Use this checklist for a release you intend
to share with real users. Do not publish logs, customer failures, AWS
credentials, access keys, session tokens, personal information, **or growth/outreach notes**
into git history. Keep operational notes (including outreach/distribution tracking)
in local, ignored paths such as `notes/` (kept out of git history).

## 1. Release preflight

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/sync-site-metadata.py
python -m build
python -m sam_doctor.cli demo
```

Confirm that the version in `pyproject.toml`, `src/sam_doctor/__init__.py`,
`CHANGELOG.md`, and the release note all agree.

For a quick machine-check before tag push, run:

```powershell
python scripts/check-launch.py --skip-outreach
python scripts/check-launch.py --skip-distribution \
  --outreach-log notes/sam-doctor-outreach-log.csv \
  --outreach-summary notes/sam-doctor-outreach-summary.md \
  --strict-ethical --min-feedback-ratio 100
python scripts/check-launch.py \
  --strict-distribution-during-release \
  --strict-ethical --min-feedback-ratio 100 \
  --outreach-log notes/sam-doctor-outreach-log.csv \
  --outreach-summary notes/sam-doctor-outreach-summary.md
```

Daily launch tracking files are local-only by default:

- `notes/distribution.csv`
- `notes/distribution-summary.md`
- `notes/sam-doctor-outreach-log.csv`
- `notes/sam-doctor-outreach-summary.md`

These paths are ignored by git, so growth/outreach notes stay in your working copy
only and are never committed.

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
8. Stable release publishes trigger `distribution-check.yml` automatically for a
   baseline run, then `pypi-publish.yml` triggers a strict rerun with
   `strict-distribution-during-release=true` after PyPI upload.

For the GitHub Action listing, follow `launch/MARKETPLACE.md` after the
repository owner has reviewed and accepted GitHub's Marketplace Developer
Agreement.

If you want the distribution snapshot to fail on hard launch-channel readiness
after publish, trigger `distribution-check.yml` manually and enable:

- `strict-distribution-during-release: true`
- (Optional for founder checks) `strict-ethical: true`
- (Optional) `min-feedback-ratio` to set your ethical ratio bar (example: `100`)

## 3. First distribution

Use a local outreach note file (for example `notes/sam-doctor-launch-notes.md`) for personalized conversations with developers who have a recent, public SAM, CloudFormation, IAM, or GitHub Actions error.
Keep that note file outside the repository so it is never committed.
Lead with the free tool and ask for one sanitized failure. Ask for founder payment only after the report proves useful.

Use `python scripts/check-distribution.py` periodically (or before major outreach bursts)
to confirm star growth, GitHub activity, and channel visibility remain on track.

## Definition of the first revenue milestone

Three $39 founder purchases from people who are not friends or family. Record the buyer type, problem, acquisition channel, and feedback without storing their logs or credentials.

Use `--outreach-log` to point to your local outreach file:

```powershell
python scripts/bootstrap-outreach-log.py notes/sam-doctor-outreach-log.csv
python scripts/check-launch.py --skip-distribution --outreach-log notes/sam-doctor-outreach-log.csv --outreach-summary notes/sam-doctor-outreach-summary.md
```
