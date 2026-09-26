---
name: git_workflow
description: Use when committing, branching, or staging changes, and whenever writing git commit messages.
---
# Git Workflow

Safe, clean git operations with conventional commit messages.

## Before any commit
1. `git status` — see what exists and what's staged.
2. Briefly review changes using `git diff --stat`. Only read the full `git diff` or `git diff --staged` if the changes are small or if you need specific details to write a good commit message. For large diffs, avoid reading the entire output unless strictly necessary.
3. Keep an eye out for secrets (keys, tokens, `.env`, credentials) when reviewing code, but a full scan of the diff is only required if the user specifically requests it or the task involves sensitive files. If found, stop and warn.
4. Check you are on the intended branch: `git branch --show-current`. Don't commit directly to `main`/`master` unless the user asked.

## Staging
- Stage specific files (`git add path/to/file`) rather than `git add -A` so unrelated edits aren't swept in.
- Group changes into focused commits: one logical change per commit. If a commit mixes a refactor and a feature, split it.
- Use `git add -p` when only part of a file belongs in this commit.

## Commit messages (Conventional Commits)
Format: `type(scope): summary`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.
- Summary: imperative mood, lowercase, no trailing period, ≤72 chars ("add retry to client", not "added retries.").
- Body (after a blank line): explain **what** and **why**, not how. Wrap at 72 chars.
- Add `BREAKING CHANGE:` in the body for incompatible changes.

Examples:
```
feat(auth): add refresh-token rotation

Rotate the refresh token on every use so a leaked token
cannot be reused indefinitely. Closes #142.
```
```
fix(parser): handle empty input without crashing

Previously an empty string raised IndexError. Return an empty
result instead and cover it with a test.
```

## History hygiene
- Amend unpushed mistakes with `git commit --amend`; don't amend commits already pushed to a shared branch.
- Prefer `git revert` over history rewriting on shared branches.
- Getting out of trouble: `git restore <file>` (discard working changes), `git reset --soft HEAD~1` (undo last commit, keep changes), `git stash` / `git stash pop`.

## Pushing & PRs
- Verify with `git log --oneline -5` that the history reads cleanly before pushing.
- Push the branch and give the user the PR-ready summary: title, what changed, why, and how it was tested.

## Never
- Never force-push a shared branch (`main`, `develop`, a teammate's branch) without explicit instruction.
- Never run `git reset --hard` or `git clean -fd` on work you haven't confirmed is disposable.
- Never commit `.env`, credentials, or large binaries.
