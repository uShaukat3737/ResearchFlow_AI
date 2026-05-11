# Commit Discipline

## Format

```
<type>(<scope>): <what changed>
```

Types: `test`, `fix`, `feat`, `refactor`, `docs`, `chore`

Scope: the module or area changed — e.g., `clarity`, `research`, `validator`, `synthesis`, `graph`, `state`, `prompts`, `main`, `claude`

## TDD Commit Pairs

Every bug fix or feature must produce exactly two commits:

```
test(clarity): assert unlisted company clears in fallback [RED]
fix(clarity): replace 7-company list with heuristic detection [GREEN]
```

The `[RED]` commit contains only the new failing test.
The `[GREEN]` commit contains only the minimum implementation to make it pass.

## Never Commit

- `.env` or any file matching `*.env*`
- `__pycache__/`, `*.pyc`, `.pytest_cache/`
- `.venv/`
- Files with hardcoded secrets or API keys

## ADR Commits

ADR documents are committed standalone before the implementation fix:

```
docs(adr): ADR-003 research data deduplication strategy
fix(research): deduplicate research_data by URL on retry [GREEN]
```

## Reviewer Finding Commits

Fixes resulting from reviewer findings use:

```
fix(<scope>): <finding summary> — per reviewer finding [CATEGORY]
```

Example:
```
fix(validator): add HumanMessage to structured_llm invoke — per reviewer MISSING_EDGE_CASE
```
