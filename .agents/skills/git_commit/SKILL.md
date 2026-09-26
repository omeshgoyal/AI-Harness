---
name: git_commit
description: Write clean, conventional commit messages for staged changes.
---
When the user asks for a commit message (or asks you to commit):

1. Run `git status` and `git diff --staged` to inspect what is staged.
   - If nothing is staged, run `git diff` and note that in your reply.
2. Summarize the change in one imperative subject line, <= 72 characters,
   using Conventional Commits: `type(scope): summary`.
   Valid types: feat, fix, docs, style, refactor, perf, test, build, ci, chore.
3. If the change is non-trivial, add a body separated by a blank line:
   explain WHAT changed and WHY (not HOW). Wrap at 72 characters.
4. Reference issues with `Refs: #123` / `Closes: #123` when relevant.

Output the message in a fenced code block so the user can copy it.
Never invent file names — only reference files that actually appear in the diff.
