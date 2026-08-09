# Publish a SAM Doctor release

This repository is already public. Use this checklist for a release you intend
to share with real users. Do not publish logs, customer failures, AWS
credentials, access keys, session tokens, or personal information into git
history. Keep operational notes in local, ignored paths such as `notes/`.

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

For a quick machine-check of repository release readiness before publishing, run:

```powershell
python scripts/check-launch-readiness.py --repo jakegold1647/sam-doctor
```

## 2. Publish the public tool

1. Open the repository's Actions tab and confirm the `Verify free core` workflow passes.
2. Create and push the matching `vX.Y.Z` tag, then open **Actions -> Publish
   release -> Run workflow** on `main` and enter that exact tag. The workflow
   accepts only a tag on the reviewed `main` history. It builds the wheel and
   source archive without write permission, then transfers the verified bytes
   to the release job. Plain semantic version tags (such as `v0.7.4`) create a
   regular release; pre-release tag names (such as `v0.7.4-rc.1`) create a
   prerelease using `launch/RELEASE-${TAG}.md` when present.
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

For the GitHub Action listing, follow `launch/MARKETPLACE.md` after the
repository owner has reviewed and accepted GitHub's Marketplace Developer
Agreement.
