---
name: write_tests
description: Write focused, reliable tests for existing code.
---
When asked to add tests:

1. Read the target module with `read_file` to learn its real API, edge cases,
   and error paths. Do not invent function signatures.
2. Match the project's existing framework and layout (check for pytest/unittest,
   a `tests/` dir, and naming conventions) — run `ls` / `read_file` to confirm.
3. Cover, at minimum:
   - the happy path,
   - boundary values (empty, zero, max),
   - error/invalid input raises the expected exception.
4. One behavior per test; names should read as a sentence
   (`test_parse_rejects_negative_amount`).
5. Prefer plain asserts and small fixtures over heavy mocking.
6. After writing, RUN the tests with `bash` and fix any failures.
   Report the final passing output.
