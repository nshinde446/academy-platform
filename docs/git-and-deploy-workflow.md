# Git & Deployment Workflow — standard practice

The repo is trunk-based on `master`. `master` is always deployable; every change
reaches it through a short-lived branch + PR. Production deploys automatically on
push to `master`.

## The loop (every change)

1. **Branch off fresh `master`** — never commit to `master` directly.
   ```bash
   git checkout master && git pull --ff-only origin master
   git checkout -b feat/<short-topic>     # or fix/, chore/, ci/, docs/
   ```

2. **Commit** in logical units. Conventional-commit subject, imperative mood,
   and the co-author trailer:
   ```
   <type>(<scope>): <summary>

   <body — what & why>

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
   ```
   Types: `feat`, `fix`, `ci`, `chore`, `docs`, `refactor`, `test`.
   Stage explicit paths (`git add <paths>`), not `git add -A` — the repo carries
   untracked scratch dirs (`misc/`, `study_material/`) that must not be committed.

3. **Push the branch & open a PR** — never push straight to `master`.
   ```bash
   git push -u origin <branch>
   gh pr create --base master --title "<type>(scope): …" --body-file <file>
   ```
   The PR is the gate: CI (`.github/workflows/ci.yml`) runs the full backend
   pytest + frontend vitest suites on it.

4. **Merge once CI is green** — squash + delete branch:
   ```bash
   gh pr merge <n> --squash --delete-branch        # after checks pass
   # or arm it to merge itself when green (see gotcha below):
   gh pr merge <n> --squash --auto --delete-branch
   ```

5. **Deploy is automatic.** Pushing to `master` triggers
   `Deploy / production`: it re-runs the suites as a `gate-tests` job, builds
   backend + frontend images (tagged by SHA), waits for the `production`
   environment approval, then SSH-deploys to the VPS.

6. **Verify prod** after the deploy completes — confirm the run succeeded and do
   a lightweight read-only reachability check (e.g. `GET /login` → 200,
   an authed API route → 401). Prod app: `https://app.eduworld-livekit.duckdns.org`.

## ⚠️ Gotcha: `--auto` only waits if branch protection requires checks

`gh pr merge --auto` is supposed to wait for green CI before merging. But GitHub
only enforces that wait when the branch has **branch protection with required
status checks**. Without it, `--auto` *merges immediately* even while checks are
still pending. We hit this on PR #10 — it merged through with CI pending.

It was still safe because the deploy's `gate-tests` re-runs the full suite before
shipping (a red suite halts the deploy, not just the merge) — but the PR gate was
effectively bypassed.

**Fix / recommended setup:** enable branch protection on `master`
(Settings → Branches, or via API) requiring `backend-tests` and `frontend-tests`
to pass before merge. Then `--auto` truly waits, and direct pushes are blocked.
```bash
gh api -X PUT repos/<owner>/<repo>/branches/master/protection \
  -H "Accept: application/vnd.github+json" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=backend-tests' \
  -f 'required_status_checks[contexts][]=frontend-tests' \
  -F 'enforce_admins=false' \
  -f 'required_pull_request_reviews=' -F 'restrictions='
```

## Keeping deploys fast (without weakening gates)

- The deploy `gate-tests` calls CI with `fast: true` → it runs **only** the unit
  suites that gate a release and skips Playwright e2e, the coverage re-run, and
  security scans. Those still run in full on every PR/push.
- **Build once, promote the artifact.** Images are tagged by SHA and the deploy
  ships that exact image — don't rebuild at deploy time.
- **Don't babysit CI.** Use `--auto` (with branch protection) and let the deploy
  notify you. Optimize *your attention time*, not the machine time.
- Bigger win (not yet done): skip `gate-tests` entirely for a SHA whose PR CI is
  already green, or adopt a merge queue — removes the one full-suite re-run.

## Quick reference

| Action | Command |
|---|---|
| New branch | `git checkout master && git pull --ff-only && git checkout -b feat/x` |
| Commit | `git add <paths> && git commit -F <msgfile>` |
| Push + PR | `git push -u origin feat/x && gh pr create --base master …` |
| Watch CI | `gh pr checks <n>` |
| Merge when green | `gh pr merge <n> --squash --delete-branch` |
| Deploy | automatic on merge to `master` |
| Verify prod | `curl -s -o /dev/null -w '%{http_code}' https://app.eduworld-livekit.duckdns.org/login` |
