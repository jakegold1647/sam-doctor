# Publishing SAM Doctor to PyPI

SAM Doctor's release workflow publishes a normal release for plain version tags and
publishes prereleases for tags with pre-release suffixes. PyPI publishes on the
`release` GitHub event only when the release is not marked as a prerelease.

## One-time owner setup

1. Sign in to [PyPI's publishing settings](https://pypi.org/manage/account/publishing/)
   and add a **pending GitHub Actions publisher** with these values:
   - PyPI project name: `sam-doctor`
   - Owner: `jakegold1647`
   - Repository: `sam-doctor`
   - Workflow filename: `pypi-publish.yml`
   - Environment name: `pypi`
2. In the GitHub repository, configure the existing `pypi` environment with the
   desired deployment protection rule or reviewers before the first stable release.
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

The release workflow explicitly dispatches `pypi-publish.yml` for stable tags
because releases created with the repository `GITHUB_TOKEN` do not fan out a
second workflow from the `release` event. Both that dispatch and the strict
post-publish health check run from `main`, where the current workflow definition
is available. The publisher then checks out the requested release tag before
building, so the package contents stay tied to the release being recovered.

To retry a stable publication, run the PyPI workflow manually and provide the
same `release-tag` value. In the GitHub UI, open **Actions -> Publish to PyPI ->
Run workflow**, choose `main` as the workflow ref, and enter the stable release
tag (for example, `v0.7.6`) in `release-tag`.

The workflow uses PyPI Trusted Publishing with a short-lived GitHub Actions OIDC
token. It does not require a long-lived PyPI API token in repository secrets.
