# What stands between here and 1.0

A short punch list, kept honest. 1.0 does not mean "every rule exists"; it
means a user can rely on what is already here.

1. Keep the release channels in step. Stable releases ship to PyPI and to a
   GitHub tag automatically, but the GitHub Marketplace listing has to be
   republished by hand after each release. The republish step is step 6 of the
   checklist in [pypi-publishing.md](pypi-publishing.md); what remains is
   following it on the next release and confirming the listing updates.
2. Keep the rule-request tracker honest. [#79](https://github.com/jakegold1647/sam-doctor/issues/79)
   is assigned to a contributor, so it is not available for duplicate work.
   [#63](https://github.com/jakegold1647/sam-doctor/issues/63) still needs a
   complete sanitized reproduction before implementation. #21 and #66 are
   implemented and closed. Entry 14 in
   [rule-roadmap.md](rule-roadmap.md) should land or be explicitly deferred
   before 1.0.
3. Promise stability. The JSON report shape, the stable rule ids (landed in
   #47 and now carried through JSON, SARIF, the fixture registry, and the
   error-page map), and the CLI flags are what CI integrations depend on.
   The promise is drafted in [stability.md](stability.md); at 1.0 the README
   links to it and it stops being a draft. Until then, 1.0 is a version
   number, not a commitment.
4. Keep the site in step. Done and enforced: every rule has a dedicated
   error-reference page, and `scripts/check-error-pages.py` fails when a
   catalog rule has no mapping entry - so a new rule cannot land without its
   page. The gate also still catches renamed rules, missing pages, and
   orphaned or unlinked pages.
5. Nothing else. Resist adding scope here: the catalog grows through the
   roadmap and rule requests at its own pace, before and after 1.0.
