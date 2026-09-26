---
name: code_review
description: Perform a structured, high-signal code review of a file or diff.
---
When asked to review code:

1. Read the target with `read_file`, or `git diff` for a diff review.
2. Report findings grouped by severity, highest first:
   - **Blocker**: bugs, security holes, data loss, crashes.
   - **Major**: logic errors, race conditions, missing error handling.
   - **Minor**: readability, naming, duplication.
   - **Nit**: style preferences.
3. For every finding give: file, approximate line, the problem,
   and a concrete suggested fix (show code when short).
4. Explicitly call out what is GOOD so the author knows what to keep.
5. End with a one-line verdict: Approve / Approve with comments / Request changes.

Be specific and evidence-based. Do not pad the review with generic advice.
