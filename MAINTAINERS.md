# Maintainers

SAM Doctor is maintained in the open. The current maintainer is
[@jakegold1647](https://github.com/jakegold1647), and the project is intentionally
building toward a small group of people who can share triage, reviews, and
release responsibility.

## How maintenance works

- Issues and pull requests are welcome from people outside the maintainer
  team.
- A focused change, a reproducible report, or a helpful review is a meaningful
  contribution. You do not need to ask for permission before opening a draft
  pull request.
- `main` stays protected by the required checks. `staging` is the shared lane
  for maintainer integration work; it does not publish the site or a release.
- Decisions follow the evidence boundary: keep fixtures sanitized, prefer a
  supported finding over a guess, and leave the project saying "unknown" when
  the log does not support more.

## Becoming a co-maintainer

There is no application form and no expectation that one person takes over the
whole repository. The usual path is to contribute, help with a review, join
issue triage, and then take on a small, explicit responsibility with a second
maintainer nearby. The full path and handoff checklist live in
[docs/maintainer-path.md](docs/maintainer-path.md).

If you would like to grow into that role, leave a note in a relevant issue or
discussion and start with a scoped task from the
[ready newcomer queue](https://github.com/jakegold1647/sam-doctor/issues?q=is%3Aissue+is%3Aopen+label%3A%22status%3A+ready%22+label%3A%22mentor%20available%22).
We will keep the scope clear, pair on the first review, and expand access only
when the work and the schedule make that sensible.

## When the primary maintainer is away

Start with the open issue queue, the community triage checklist, and the
staging branch. Before promoting a change to `main`, run the same gate used by
CI and keep contributor credit synchronized through `CONTRIBUTORS.md` and
`python scripts/sync-contributor-page.py`.

For the complete handoff checklist, see
[docs/maintainer-path.md](docs/maintainer-path.md).
