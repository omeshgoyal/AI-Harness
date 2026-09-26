---
name: debug_python
description: Systematically diagnose and fix a Python bug or traceback.
---
When the user reports a Python error or unexpected behavior:

1. Reproduce it. Run the failing command with `bash` and capture the full traceback.
2. Read the actual traceback bottom-up: the last frame is where it broke;
   the real cause is often a frame or two above.
3. Form ONE hypothesis at a time and test it with a minimal repro
   (a short `python -c "..."` or a temp script). Do not change many things at once.
4. Inspect the offending code with `read_file` before proposing a fix.
5. Apply the smallest fix that addresses the root cause, then re-run to confirm.
6. State clearly: root cause, the fix, and how you verified it.

Never guess-fix by adding broad try/except. Never edit code you have not read.
