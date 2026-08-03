# Publish a SAM Doctor release

This repository is already public. Use this checklist for a release you intend
to share with real users. Do not publish logs, customer failures, AWS
credentials, access keys, session tokens, or personal information.

## 1. Release preflight

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
sam-doctor demo
```

Confirm that the version in `pyproject.toml`, `src/sam_doctor/__init__.py`,
`CHANGELOG.md`, and the release note all agree.

## 2. Publish the public tool

1. Open the repository's Actions tab and confirm the `Verify free core` workflow passes.
2. Push the matching `vX.Y.Z` tag. The `Publish release` workflow builds the
   wheel and source archive. It creates a regular release for plain semantic
   version tags (such as `v0.7.4`) and a prerelease for pre-release tag names
   (such as `v0.7.4-rc.1`) using `launch/RELEASE-${TAG}.md` when present.
3. Confirm GitHub Pages serves the current `site/` directory.
4. In repository Settings, set the homepage to the GitHub Pages URL and add these
   topics: `aws`, `aws-sam`, `cloudformation`, `github-actions`, `iam`,
   `serverless`, `python`, `cli`.
5. Upload `site/assets/sam-doctor-social-preview.jpg` as the repository's social
   preview image.
6. If this tag includes a pre-release suffix, convert to full release only after
   internal sign-off. For plain `vX.Y.Z` releases, Marketplace and PyPI publish
   flows can use the release as soon as release notes and checks are green.

For the GitHub Action listing, follow `launch/MARKETPLACE.md` after the
repository owner has reviewed and accepted GitHub's Marketplace Developer
Agreement.

## 3. Prepare a founder checkout only after validation

Create a Lemon Squeezy one-time product using `launch/PRODUCT-LISTING.md`.

Do not activate a purchase button until the product description includes the delivery condition and refund terms. Then replace the `YOUR_STORE` and `YOUR_PRODUCT` placeholders in `site/index.html` with the checkout URL.

## 4. First distribution

Use `launch/LAUNCH-PLAN.md` and `launch/OUTREACH.md` for personalized conversations with developers who have a recent, public SAM, CloudFormation, IAM, or GitHub Actions error. Lead with the free tool and ask for a sanitized failure. Ask for founder payment only after the report proves useful.

Use `python scripts/check-distribution.py` periodically (or before major outreach bursts)
to confirm star growth, GitHub activity, and channel visibility remain on track.

## Definition of the first revenue milestone

Three $39 founder purchases from people who are not friends or family. Record the buyer type, problem, acquisition channel, and feedback without storing their logs or credentials.

