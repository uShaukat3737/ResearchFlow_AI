# Skill: Fix Agent Bug (TDD-Compliant)

## Trigger

Use when a confirmed bug in an agent file needs to be fixed. Parameters: `[agent_file]`, `[bug_description]`, `[test_function_name]`.

## Steps

1. **Read the file** — read `[agent_file]` in full, identify the exact lines involved in the bug
2. **Write the failing test** — add `[test_function_name]` to the appropriate test file; assert the *correct* behavior, not the current broken behavior
3. **Confirm RED** — run `pytest tests/` and verify: (a) only the new test fails, (b) the failure message shows the broken behavior
4. **Commit `[RED]`** — `test(<scope>): [test_function_name] [RED]`
5. **Apply the fix** — change only the lines needed to make `[test_function_name]` pass; do not refactor unrelated code
6. **Confirm GREEN** — run `pytest tests/` and verify all tests pass
7. **Commit `[GREEN]`** — `fix(<scope>): [bug_description] [GREEN]`
8. **Invoke reviewer** — call `langgraph-assistant-reviewer` on the modified file per `reviewer-trigger-protocol.md`
9. **Address findings** — for each CRITICAL/HIGH finding: write a test → fix → commit; for each finding that changes a design decision: write ADR first

## Abort Condition

If step 6 produces a new unexpected failure on a previously passing test, do NOT commit. Investigate the regression before proceeding.
