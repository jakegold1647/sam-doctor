# What stands between here and 1.0

A short punch list, kept honest. 1.0 does not mean "every rule exists"; it
means a user can rely on what is already here.

1. Keep the release channels in step. 0.8.x ships to PyPI and to a GitHub tag
   automatically, but the GitHub Marketplace listing has to be republished by
   hand after each release. Until that is part of the release checklist,
   Action users can sit on an older version than PyPI users get.
2. Settle the open rule requests. #24 is assigned; #28-#33 are open for
   contributors. Each should land or be explicitly deferred before 1.0 so the
   issue tracker reflects reality, not ambition.
3. Promise stability. The JSON report shape and the CLI flags are what CI
   integrations depend on. The promise is drafted in
   [stability.md](stability.md); at 1.0 the README links to it and it stops
   being a draft. Until then, 1.0 is a version number, not a commitment.
4. Keep the site in step. Error-reference pages are hand-written; a release
   that adds rules without pages quietly breaks the "every rule is
   documented" impression the site gives. Add a release-checklist item (or a
   QA check) that counts rules against pages.
5. Nothing else. Resist adding scope here: the catalog grows through the
   roadmap and rule requests at its own pace, before and after 1.0.
