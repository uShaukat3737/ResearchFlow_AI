# ADR-000: Literal Types for Routing Signal Fields

**Date:** 2026-05-11
**Status:** Accepted
**Decider:** Claude Code session — Phase 1 / langgraph-assistant-reviewer

## Context

The `ResearchAssistantState` TypedDict contains fields whose values are consumed exclusively by LangGraph conditional-edge routing functions (`route_clarity`, `route_research`, `route_validator`). In the starter code these were typed as bare `str`:

```python
clarity_status: str             # "clear" | "needs_clarification"
validation_result: str          # "sufficient" | "insufficient"
```

The comments are the only contract. A node that writes an unrecognised value (e.g. `"clarified"`, `"unclear"`) passes type-checking silently and causes the routing function to return an unintended edge key — either routing to the wrong node or raising a `KeyError` with no helpful error message.

This was flagged as `[SEVERITY: HIGH][CATEGORY: STATE_MANAGEMENT]` by the `langgraph-assistant-reviewer` during Phase 1.

## Decision

All state fields whose values are consumed by LangGraph conditional-edge functions MUST be typed with `Literal[...]` rather than bare `str`:

```python
from typing import Literal

clarity_status: Literal["clear", "needs_clarification"]
validation_result: Literal["sufficient", "insufficient"]
```

**Policy extension**: Any future routing signal field added to `ResearchAssistantState` must use `Literal` enumeration of all permitted values before being merged.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Keep bare `str` with comment | Comment is not enforced; survives refactors silently |
| Use `Enum` class | More ceremony for no benefit — `Literal` is idiomatic for LangGraph state fields; avoids import complexity in routing functions |
| Runtime validation in routing functions | Adds guard clauses to routing code; doesn't catch the bug at the write site (in the agent), only at the read site |

## Consequences

### Positive
- Static type-checkers (`mypy`, `pyright`) will flag any agent that writes a value outside the `Literal` set
- Routing bugs from typos become immediate type errors, not silent misbehaviours
- The permitted values are self-documenting in the schema — no comment needed
- Establishes a reviewable policy for all future routing fields

### Negative / Trade-offs
- TypedDict `Literal` fields are more verbose
- Slightly more friction when adding new routing states (must update the `Literal` definition)

### Files Affected
- `app/schemas/state.py` — change `clarity_status: str` and `validation_result: str`
- `tests/test_graph.py` — add `test_clarity_status_is_literal_type` and `test_validation_result_is_literal_type`

## Related

- Reviewer finding: `[SEVERITY: HIGH][CATEGORY: STATE_MANAGEMENT]` — Phase 1
- Tests: `test_clarity_status_is_literal_type`, `test_validation_result_is_literal_type`
- Routing functions that consume these fields: `route_clarity` (`app/graph/routing.py:4`), `route_validator` (`app/graph/routing.py:23`)
