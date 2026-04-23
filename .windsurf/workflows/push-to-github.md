---
description: Push local changes to GitHub (status → commit → push)
---

Triggered when the user says "push to github" (or similar).

1. Show the current branch and working tree state so the user can see what will be committed.
// turbo
```
git status --short --branch
```

2. Show a concise diff summary (file-level stats) for staged + unstaged changes.
// turbo
```
git diff --stat HEAD
```

3. If there are no changes to commit, stop and report that the tree is clean. Otherwise continue.

4. Propose a commit message based on the diff:
   - Use Conventional Commits style (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
   - Subject line <= 72 chars, imperative mood, no trailing period.
   - Add a short body only if the change touches multiple areas.
   - Present the proposed message to the user and wait for confirmation or an edit before committing.

5. Check the current branch.
// turbo
```
git rev-parse --abbrev-ref HEAD
```

6. **If the current branch is `main` or `master`**, auto-create a feature branch so the protected branch is never pushed to directly:
   - Derive a slug from the commit subject: lowercase, replace non-alphanumerics with `-`, collapse repeats, trim to ~40 chars, strip the Conventional Commits type prefix (e.g. `feat:`) before slugging.
   - Prefix with the commit type when available, e.g. `feat/add-push-workflow` or `fix/null-check-on-signals`. Fallback prefix: `chore/`.
   - If the branch name already exists locally or on `origin`, append a short timestamp suffix like `-20260423`.
   - Create and switch to it (this carries the uncommitted changes with you):
     ```
     git checkout -b <branch-name>
     ```
   - Tell the user which branch was created and why.

   **Otherwise** (already on a feature branch), stay on it.

7. Stage all changes.
// turbo
```
git add -A
```

8. Commit with the confirmed message. Use `-m` (and a second `-m` for the body if present). Never use `--no-verify`.

9. Push to the current branch. Always use `git push -u origin HEAD` so newly created branches get an upstream set on the first push.
// turbo
```
git push -u origin HEAD
```

10. Report the result: commit SHA, branch name, and (if the remote is GitHub) a suggested PR URL of the form `https://github.com/<owner>/<repo>/compare/<branch>?expand=1`. Derive `<owner>/<repo>` from `git remote get-url origin`.

11. If the push was rejected (non-fast-forward), stop and ask the user before running `git pull --rebase` or force-pushing — never force-push without explicit confirmation, and never force-push to `main`/`master` at all.
