# Git Flow

Every change lands the same way: a branch, a pull request, a green CI run, a
squash merge into `main`. Nothing is committed to `main` directly.

## The steps

1. Branch off an up-to-date `main`:

   ```bash
   git switch -c fix/reading-log-order main
   ```

2. Commit in the repo's Conventional Commits style, the prefix naming the kind of
   change: `fix(history)`, `feat(series)`, `docs(agents)`, `chore(deps)`. The body
   says why the change is needed, not what the diff does.

3. Push the branch and open a pull request:

   ```bash
   gh pr create --fill
   ```

4. Wait for CI. Both jobs have to pass: `test` and `lint-and-format`.

5. Squash merge, which keeps `main` linear and puts the pull request number in
   the subject — `fix(ui): … (#123)` — then delete the branch:

   ```bash
   gh pr merge --squash --delete-branch
   ```

## The pull request body

Write it for whoever reads it in six months: why the change is needed, what it
changed, and what was verified. Say plainly when a check could not run, or when a
verification was manual rather than automated, rather than leaving it out.

Name the issue with `Closes #NNN` so the tracker closes it on merge.

## Why

`main` is what deploys, so a commit on it should have been reviewed and should
have passed CI before it landed. That review needs somewhere to happen, and a
commit message cannot hold a discussion.

It also matters for required status checks: issue #331 adds an end-to-end suite
as one, and a required check can only gate work that arrives through a pull
request.

## Exceptions

Dependabot's own pull requests are squash-merged for it once they are mergeable,
by `.github/workflows/dependabot-auto-merge.yml`. They still arrive as pull
requests and still run CI.
