# A maintainer path that can outgrow one person

SAM Doctor should be useful even when its original maintainer is busy. The
project is deliberately building a path from contributor to trusted co-
maintainer instead of assuming one person will answer every question forever.

This is a gradual handoff, not an automatic permission grant. Nobody needs to
volunteer for a role, and a contributor can stay focused on code, docs, triage,
or community support without taking on broader responsibility.

## The path

1. **Contributor:** ships a focused change, a reproducible report, or a useful
   fixture. The work is reviewed in the normal pull-request flow and credited
   in the [Hall of Fame](https://sam-doctor.jacobgoldstein.dev/contributors/).
2. **Regular reviewer:** helps another contributor with fixtures, evidence
   boundaries, documentation, or a small review. Reviews should be kind,
   specific, and grounded in what the tests and logs actually show.
3. **Triage collaborator:** helps keep the issue queue usable: welcomes a
   claimant, spots duplicate work, asks for redaction, and turns a vague report
   into a scoped next step. The [community triage checklist](community-triage.md)
   is the shared playbook.
4. **Co-maintainer:** can shepherd a change from issue to green checks and
   release-ready review, knows the staging lane, and can keep the community
   moving when the primary maintainer is unavailable.

The steps do not have to happen in a fixed order. A person who is excellent at
community support may be the right future co-maintainer even if they never add
a diagnostic rule.

## What earns trust

The useful signals are boring and observable:

- a few focused contributions that keep their scope and preserve evidence;
- thoughtful reviews that help people finish instead of merely pointing out
  mistakes;
- reliable use of the PR gate and the shared `staging` testing ground;
- good judgment about redaction, privacy, and when the tool should say
  “unknown”;
- clear handoffs in issues and discussions, including saying when something is
  blocked.

Stars, volume, and being online at a particular hour are not requirements.

## How we make the handoff safely

- Start with paired reviews and a small, explicit responsibility. Keep the
  permission scope no wider than the work requires.
- Write down the decision in the issue or discussion so the community knows
  who is carrying the next step.
- Keep `main` protected and use `staging` for maintainer integration work. A
  co-maintainer should be comfortable reading the green checks before merging,
  not bypassing them.
- Review access as the project changes. A role can be paused or handed back
  without drama if someone's schedule changes.
- When a co-maintainer is ready, add them to the repository's maintainer
  settings deliberately and update this document with the new ownership
  boundary.

## If Jacob is unavailable

The next maintainer should be able to find, in the repository and its linked
workflows:

1. the open issue queue and any claimed work;
2. the contributor records and the sync command that updates the README and
   website Hall of Fame;
3. the `staging` branch and the checks required before promoting to `main`;
4. the community triage and outreach playbooks; and
5. the release and publishing checks, including the rule-catalog and package
   gates.

If one of those pieces is unclear, that is a documentation issue worth fixing
before a person takes on the role.
