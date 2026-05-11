# Skill: Run Test Suite

## Trigger

Use this skill whenever you need to run tests, check the suite status, or verify a change did not break existing tests.

## Command

Full suite:
```bash
.venv/bin/python -m pytest tests/ -v
```

Single test:
```bash
.venv/bin/python -m pytest tests/test_graph.py::<test_name> -v
```

Single file:
```bash
.venv/bin/python -m pytest tests/test_graph.py -v
```

## Output Interpretation

After running, report:
1. Total PASSED / FAILED / ERROR counts
2. If any unexpected failures: file path, test name, and first assertion error line
3. If all pass: confirm count and elapsed time
4. Distinguish between: "new test is RED as expected" vs "unexpected regression"

## What "RED as expected" Means

When writing a new test first (TDD), ONE test failing is correct. Confirm:
- The failing test is the one just written
- All other tests are still GREEN
- The failure message matches the expected missing behavior

## What Counts as a Blocker

- Any test other than the newly written one turns RED → stop, investigate, fix before proceeding
- A test that was GREEN becomes ERROR → dependency or import problem, fix first
