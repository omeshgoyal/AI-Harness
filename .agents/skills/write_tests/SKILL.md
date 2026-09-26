---
name: write_tests
description: Use when adding or improving automated tests, or when asked to make code testable and well-covered.
---
# Write Tests

Write tests that catch real regressions and read as documentation.

## 1. Find the project's conventions first
- Locate existing tests (`ls **/test*`, `test_*.py`, `*.test.ts`, `*_spec.rb`).
- Match the framework, layout, naming, and assertion style already in use. Detect it: check `package.json`, `pyproject.toml`, `pytest.ini`, `Makefile` for the test command.
- Run the existing suite once before adding anything so you know the baseline and the exact command.

## 2. Decide what to test
Cover, in priority order:
1. **The happy path** — normal input produces the expected result.
2. **Boundaries** — empty, single element, max size, zero, negative, off-by-one.
3. **Error/failure paths** — invalid input, missing file, network error; assert the *specific* error.
4. **Regression cases** — the exact bug that was just fixed (add it so it can't come back).
5. **Side effects** — state changed, calls made, files written.

Don't test third-party libraries or trivial getters. Prefer testing the public interface over private internals.

## 3. Structure: Arrange – Act – Assert
```
def test_discount_is_capped_at_50_percent():
    # Arrange
    cart = Cart(subtotal=1000)
    # Act
    total = cart.apply_discount(0.8)
    # Assert
    assert total == 500
```
- One behavior per test. If the name needs "and", split it.
- Name tests after the behavior: `test_<unit>_<condition>_<expected>`.

## 4. Make tests trustworthy
- Assert on concrete values, not just "didn't throw". `assert result == 3` beats `assert result is not None`.
- Use exact expected values; avoid recomputing them with the same logic under test.
- Keep tests independent: no shared mutable state, no reliance on execution order. Reset fixtures/setup each time.
- Deterministic only: no real network, clock, or random without seeding. Inject or mock those dependencies.
- Mock at the boundary you don't own — don't mock the thing you're testing.

## 5. Verify the tests are real
- Run the new tests and confirm they pass.
- For each new test, deliberately break the code (or flip an expected value) and confirm the test **fails**. A test that never fails proves nothing.
- Run the whole suite to ensure you didn't break existing tests.

## 6. Report
Give the test command you ran and the result summary (passed/failed counts). State which behaviors are now covered and any important gaps you intentionally left.
