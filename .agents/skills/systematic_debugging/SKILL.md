---
name: systematic_debugging
description: Use when diagnosing a bug, crash, failing test, or unexpected behavior that needs root-cause analysis rather than guessing.
---
# Systematic Debugging

Debug by forming and testing hypotheses, not by randomly editing code. Never "fix" a bug you cannot reproduce and explain.

## 1. Reproduce reliably
- Get the smallest command/input that triggers the failure. Run it and capture the exact output and stack trace.
- If you can't reproduce it, that is the first problem to solve — gather the environment, inputs, and version details that differ.
- Confirm it fails for the stated reason, not a different one.

## 2. Read the actual error
- Read the full stack trace bottom-up: the last frame in *your* code is usually the culprit.
- Note the exact exception type and message. Search the codebase for where it's raised.
- Do not skim past a warning that appears right before the crash.

## 3. Locate, don't guess
Bisect the problem space:
- Add temporary logging or `print`/`assert` at boundaries to see where state is wrong.
- Check the input at the failing boundary: is it what you assumed (`type`, `len`, `repr`)?
- Use a debugger when available (`python3 -m pdb`, `node --inspect`), or drop a breakpoint.
- For "works locally, fails in CI": diff the environment (versions, env vars, cwd, OS).

## 4. Form one hypothesis at a time
- State it explicitly: "I believe X is null because Y skips initialization."
- Predict what you'd observe if true, then test *only* that.
- Change one variable at a time. If a test disproves the guess, discard it and form the next — don't layer on more edits.

## 5. Fix the root cause
- Fix the cause, not the symptom (don't just wrap it in a try/except or widen a type).
- Prefer the fix that also prevents the whole class of bug.
- Check whether the same bug exists elsewhere: `grep -rn` for the pattern.

## 6. Prove it's fixed
- Re-run the original repro — it must now pass.
- Run the surrounding test suite to catch regressions.
- Add a regression test that fails without the fix and passes with it.

## 7. Report
Summarize:
- **Symptom**: what was observed.
- **Root cause**: the precise mechanism, with `file:line`.
- **Fix**: what changed and why it addresses the cause.
- **Verification**: the command(s) you ran and their result.

If you spent effort and still don't know, say what you ruled out and what you'd try next — never claim a fix you didn't verify.
