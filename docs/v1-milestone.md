# What stands between here and 1.0

A short punch list, kept honest. 1.0 does not mean "every rule exists"; it
means a user can rely on what is already here.

1. Cut a release. Everything in the changelog's Unreleased section (five new
   rules, the catalog gate, `check-pr.py`, the contributor docs) is on main
   but not on PyPI. PyPI still serves 0.7.7. Cutting 0.8.0 is the single
   biggest gap between the repo and what users actually install.
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
