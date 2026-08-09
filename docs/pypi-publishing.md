# Publishing SAM Doctor to PyPI

SAM Doctor's release workflow publishes a normal release for plain version tags and
publishes prereleases for tags with pre-release suffixes. After a stable release has
both package artifacts, that workflow dispatches the separate PyPI workflow from the
repository's default branch. The PyPI workflow is manual-dispatch only; it never runs
a publisher definition taken from a release tag.

## One-time owner setup

1. Sign in to [PyPI's publishing settings](https://pypi.org/manage/account/publishing/)
   and add a **pending GitHub Actions publisher** with these values:
   - PyPI project name: `sam-doctor`
   - Owner: `jakegold1647`
   - Repository: `sam-doctor`
   - Workflow filename: `pypi-publish.yml`
   - Environment name: `pypi`
2. In the GitHub repository, configure the existing `pypi` environment with a
   required reviewer before the first stable release. Keep that protection in place:
   the environment is the human approval boundary between validation and OIDC
   publication.
3. Confirm the package name is still available immediately before publishing.

The pending publisher does not reserve the package name. If another account
registers `sam-doctor` first, stop and choose a different package name rather
than attempting to take it over.

## Publishing a release

1. Update the package version, changelog, and user-facing install links.
2. Run the full test suite and build locally.
3. Create a GitHub release that is **not** marked as a prerelease.
4. Approve the `pypi` environment deployment when GitHub requests it.
5. Verify the resulting PyPI project page, install the published wheel in a
   fresh environment, and check the release files and version.
6. Republish the GitHub Marketplace listing. Marketplace does not track new
   tags automatically: open the new release in the GitHub UI, edit it, tick
   "Publish this Action to the GitHub Marketplace", and update. Skipping this
   step leaves Action users pinned to the previous listing version while PyPI
   users get the new one - the drift `docs/v1-milestone.md` item 1 warns
   about.

The release workflow creates the GitHub release with `dist/*` before it dispatches
`pypi-publish.yml` for a stable tag. The PyPI workflow accepts only a dispatch from
the current default-branch head. Before requesting environment approval, its trusted
validator:

- requires an exact `vMAJOR.MINOR.PATCH` tag with no prerelease text or leading
  zeroes;
- peels lightweight or annotated tags to a commit and checks that commit's
  `pyproject.toml` project name and version;
- requires a published, non-draft, non-prerelease GitHub release containing exactly
  the canonical wheel and source archive;
- records each GitHub asset's immutable numeric ID, non-empty size, and lowercase
  SHA-256 digest; and
- downloads both assets and verifies their digest plus the `Name` and `Version` in
  wheel `METADATA` and source-archive `PKG-INFO`.

Only after those checks pass does the `publish` job enter the protected `pypi`
environment. After approval it fetches the same validator from the already-recorded
default-branch commit, verifies the validator's own SHA-256 digest, resolves the tag
and release again, and re-downloads the same immutable asset IDs. Any tag, commit,
asset ID, name, size, digest, or package-metadata change fails the run before the
publisher requests an OIDC token. The OIDC job never checks out an operator-supplied
ref, installs build tools, or rebuilds the package.

To retry a stable publication, run the PyPI workflow manually and provide the same
`release-tag` value. In the GitHub UI, open **Actions -> Publish to PyPI -> Run
workflow**, choose the current default branch (`main`) as the workflow ref, and enter
the exact stable release tag (for example, `v0.11.0`) in `release-tag`. A stale
default-branch workflow dispatch fails and must be dispatched again.

Recovery is intentionally fail closed. A legacy release with missing, renamed,
empty, duplicate, digestless, or invalid package assets cannot publish through this
workflow. It does not fall back to rebuilding a tag. Restore independently verified
canonical assets through a separately reviewed process, or leave that release
unpublished on PyPI. Re-running a release that is already present on PyPI remains a
safe no-op because the publisher skips existing filenames only after every validation
and recheck succeeds.

The workflow uses PyPI Trusted Publishing with a short-lived GitHub Actions OIDC
token. It does not require a long-lived PyPI API token in repository secrets.
