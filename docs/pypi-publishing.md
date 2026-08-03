# Publishing a stable release to PyPI

SAM Doctor's normal GitHub releases are prereleases and deliberately do not
upload to PyPI. The repository includes a separate, least-privilege publishing
workflow for a future stable release.

## One-time owner setup

1. Sign in to [PyPI's publishing settings](https://pypi.org/manage/account/publishing/)
   and add a **pending GitHub Actions publisher** with these values:
   - PyPI project name: `sam-doctor`
   - Owner: `jakegold1647`
   - Repository: `sam-doctor`
   - Workflow filename: `pypi-publish.yml`
   - Environment name: `pypi`
2. In the GitHub repository, create an environment named `pypi` and add the
   desired deployment protection rule or reviewers before the first stable release.
3. Confirm the package name is still available immediately before publishing.

The pending publisher does not reserve the package name. If another account
registers `sam-doctor` first, stop and choose a different package name rather
than attempting to take it over.

## Publishing a stable version

1. Update the package version, changelog, and user-facing install links.
2. Run the full test suite and build locally.
3. Create a GitHub release that is **not** marked as a prerelease.
4. Approve the `pypi` environment deployment when GitHub requests it.
5. Verify the resulting PyPI project page, install the published wheel in a
   fresh environment, and check the release files and version.

The workflow uses PyPI Trusted Publishing with a short-lived GitHub Actions OIDC
token. It does not require a long-lived PyPI API token in repository secrets.
