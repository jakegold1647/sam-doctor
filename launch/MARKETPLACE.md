# Publish SAM Doctor on GitHub Marketplace

SAM Doctor is a composite GitHub Action. Its action metadata includes a concise
description and Marketplace branding; publishing is completed from a GitHub
release after the repository owner accepts the GitHub Marketplace Developer
Agreement.

## One-time account step

1. Open any SAM Doctor release and select **Edit**.
2. In **Release Action**, select **accept the GitHub Marketplace Developer
   Agreement** and review it as the repository owner.
3. Return to the release edit form after accepting the agreement.
4. Confirm this is a **published**, non-prerelease release (not a draft and not
   a prerelease). If GitHub shows
   "Latest pre-release," republish the release as stable or create a new stable
   release tag before enabling the Marketplace listing.
5. Confirm this is a **published** release (not a draft), then continue to the
   publish step.

## Publish the action

1. Select **Publish this release to the GitHub Marketplace** in **Release
   Action**.
2. Choose the most accurate Marketplace category and complete GitHub's listing
   fields from the action description and README.
3. Review the listing preview, then use GitHub's final publish control.
4. Verify the Marketplace listing displays the action description, `activity`
   icon, and yellow branding configured in `action.yml`.
5. Run the README workflow snippet in a disposable repository before sharing
   the listing broadly.
6. For this repository, use a public release tag (`vX.Y.Z`) for listing. If
   you are testing a prerelease tag (`vX.Y.Z-rc.N`), keep the listing draft
   until you have internal sign-off on the exact release path.

Do not accept the Developer Agreement or publish a Marketplace listing from an
account you are not authorized to represent.
