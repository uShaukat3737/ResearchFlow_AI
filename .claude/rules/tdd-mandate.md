# TDD Mandate — Non-Negotiable

These rules apply to every Python file change in this repository.

## The Cycle

1. Write a single failing test that asserts the desired behavior
2. Run `pytest tests/` — confirm ONLY the new test is RED, all others are GREEN
3. Commit the failing test: `test(<scope>): <description> [RED]`
4. Write the minimum implementation code to make the test pass
5. Run `pytest tests/` — confirm ALL tests are GREEN
6. Commit the implementation: `fix|feat|refactor(<scope>): <description> [GREEN]`
7. Refactor only when the full suite is green

## Hard Rules

- One test at a time. Never write two failing tests before making the first green.
- Run `pytest tests/` after **every single file change** — implementation or test.
- Never write implementation code before the test is confirmed red.
- Mock fallbacks must have at least one negative-path test (graceful failure), not only success tests.
- The failing test commit and the green implementation commit must have the same `<scope>`.

## Running tests in this project

```bash
.venv/bin/python -m pytest tests/ -v
```

Single test:
```bash
.venv/bin/python -m pytest tests/test_graph.py::test_function_name -v
```
