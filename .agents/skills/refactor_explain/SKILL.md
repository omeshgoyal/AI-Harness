---
name: refactor_explain
description: Explain or safely refactor a piece of code.
---
When asked to explain code:
- Give a one-paragraph plain-English summary of WHAT it does.
- Then walk the important lines/blocks in order.
- Define domain terms a newcomer would not know.
- End with inputs, outputs, side effects, and complexity if relevant.

When asked to refactor code:
1. Read the code first with `read_file`.
2. Ensure tests exist; if not, note that behavior is unverified and consider
   running the program to capture current output as a baseline.
3. Change one thing at a time and keep behavior identical unless told otherwise.
4. Re-run any tests/commands after each change and confirm the baseline still holds.
5. Summarize: what changed, why it is better, and any behavior differences.
