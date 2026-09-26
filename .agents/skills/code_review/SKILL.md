---
name: code_review
description: Use when asked to review a diff, pull request, or set of file changes for bugs, security issues, and quality before merging.
---
# Code Review

Review changes the way a careful senior engineer would: find real problems, not style nits.

## 0. Get the actual diff first
Never review from memory or from a summary. Establish scope:
- Uncommitted work: `git diff` and `git diff --staged`
- Against a branch: `git diff main...HEAD`
- A single commit: `git show <sha>`
- If reviewing files (not a diff), read them in full plus their tests.

State the scope you are reviewing at the top of your review.

## 1. Read for understanding before judging
- Identify what the change is *trying* to do. Read surrounding code and call sites, not just the changed lines.
- For each changed function, find its callers (`grep -rn "func_name"`) to check the contract still holds.

## 2. Check in priority order
Work down this list; stop and report anything you find at a higher tier before lower tiers.

**Correctness (highest priority)**
- Off-by-one errors, wrong comparison operators, inverted booleans.
- Null/undefined/None handling and empty-collection cases.
- Boundary conditions: empty, one element, many, duplicates, negative, zero, max.
- Error paths: is every raised/thrown error caught or propagated intentionally?
- Async/concurrency: races, unawaited promises, shared mutable state.

**Security**
- Injection: SQL, shell, template, path traversal. Look for string-built queries/commands.
- Untrusted input used without validation; auth/authorization checks skipped on a new path.
- Secrets committed (keys, tokens, passwords) — flag immediately.
- Unsafe deserialization, `eval`, or disabling TLS/CSRF checks.

**Data & state**
- Migrations reversible? Schema changes backward compatible?
- Resource leaks: unclosed files/connections/locks.
- Cache invalidation when the underlying data changes.

**API & compatibility**
- Breaking changes to public functions, signatures, or return types.
- Changed defaults, renamed fields, altered serialization.

**Tests**
- Do tests actually exercise the new behavior, including the failure path?
- Are assertions meaningful (not just "no exception")?

**Clarity (lowest)**
- Misleading names, dead code, duplicated logic, missing error messages. Keep these brief.

## 3. Verify the risky parts yourself
When something looks wrong, prove it rather than guessing:
- Write and run a tiny repro: `python3 -c "..."` or a scratch test.
- Run the existing test suite to see what actually breaks.
Report the observed result, not a theory.

## 4. Write the review
Format each finding as:
```
[severity] short title
Location: file:line
Problem: what is wrong and why it matters
Suggestion: concrete fix (with a code snippet when short)
```
Severity levels: `BLOCKER` (must fix before merge), `MAJOR`, `MINOR`, `NIT` (optional).

Rules:
- Order findings by severity.
- Be specific: quote the line, explain the concrete consequence ("if `items` is empty this divides by zero").
- Don't invent problems. If the change is solid, say so plainly.
- Separate what you verified from what you suspect.
- End with a one-line verdict: APPROVE / APPROVE WITH COMMENTS / REQUEST CHANGES.
