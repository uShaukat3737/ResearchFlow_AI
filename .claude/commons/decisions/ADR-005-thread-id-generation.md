# ADR-005: Thread ID Generation Strategy

**Date:** 2026-05-11
**Status:** Accepted
**Decider:** Claude Code session — Phase 6 / Bug #6

## Context

`main.py` used a hardcoded string `"research_session_001"` as the LangGraph `thread_id` for every CLI session.

LangGraph's `MemorySaver` checkpointer persists state keyed by `thread_id`. When two sessions share the same `thread_id`, the second session inherits all state from the first: `messages`, `clarity_status`, `attempts`, `research_data`, etc. This causes silent state pollution:

- A session that ended with `needs_clarification` leaves that status in the checkpointer. The next restart begins in clarification mode for every query, regardless of context.
- `research_data` from the previous run persists and may be passed to the new session's research agent, causing the deduplication logic to suppress all new results.
- `attempts` from a previous session carries over, potentially triggering the MAX_ATTEMPTS circuit-breaker immediately on a fresh run.

## Decision

Replace the hardcoded `thread_id` with a `uuid4()` generated at process start:

```python
import uuid
thread_id = str(uuid.uuid4())
```

This guarantees each CLI invocation gets a fresh, isolated conversation thread. `uuid.uuid4()` generates a cryptographically random 128-bit identifier with negligible collision probability.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Increment a counter (session_001, session_002) | Requires persisting counter across restarts; fragile; collision if multiple processes start simultaneously |
| Use timestamp | Millisecond collisions possible if two processes start within the same millisecond; not universally unique |
| Ask user to provide thread_id | Adds friction to the CLI; not justified for a single-user research assistant |
| Clear state on exit | Requires a shutdown hook; doesn't protect against crash or kill signals; uuid is simpler and safer |

## Consequences

### Positive
- Each CLI session starts with a clean state regardless of how the previous session ended
- No state pollution between restarts
- No session collision if multiple processes start simultaneously

### Negative / Trade-offs
- Multi-turn conversation context (clarification → follow-up) within a single CLI session still works correctly (same uuid persists for the life of the process)
- Cross-session context (e.g., user wants to resume a previous research thread) is not supported. This is an acceptable trade-off for the current single-user CLI design. A future enhancement could display the thread_id and accept `--resume <uuid>` as a CLI argument.

### Files Affected
- `main.py` — `import uuid`, replace hardcoded string with `str(uuid.uuid4())`

## Related

- Bug #6 from plan.md
- Tests: `test_two_graph_sessions_with_different_thread_ids_are_independent`, `test_graph_uses_separate_checkpointer_per_create_call`
