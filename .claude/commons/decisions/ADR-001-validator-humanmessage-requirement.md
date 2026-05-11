# ADR-001: Validator Agent HumanMessage Requirement

**Date:** 2026-05-11
**Status:** Accepted
**Decider:** Claude Code session — Phase 4 / Bug #4

## Context

`validator_agent.py` line 45 called `structured_llm.invoke([system_msg])` passing only a `SystemMessage`.

OpenAI's structured output endpoint (used by LangChain's `with_structured_output`) requires at least one `HumanMessage` in the conversation or it raises a `BadRequestError` at runtime. The bug was silent in testing because the `except Exception` fallback swallowed the error and fell through to the mock path, making it appear as if the LLM path was working.

A second issue in the same block: `AuthenticationError` and `RateLimitError` were caught by the broad `except Exception` handler and silently discarded instead of being re-raised to the caller.

Both bugs were confirmed by:
- `test_validator_agent_llm_invoke_includes_human_message` [RED → GREEN]
- `test_validator_agent_propagates_auth_error` [RED → GREEN]

## Decision

1. Add a fixed `HumanMessage` after the `SystemMessage` in the invoke call:
   ```python
   human_msg = HumanMessage(content="Analyze the research data and provide your validation assessment.")
   result = structured_llm.invoke([system_msg, human_msg])
   ```

2. Split the exception handler to re-raise unrecoverable errors before the generic fallback:
   ```python
   except (AuthenticationError, RateLimitError):
       logger.error("Validator Agent: unrecoverable OpenAI error", exc_info=True)
       raise
   except Exception as e:
       logger.warning(f"Validator Agent LLM call failed, using mock loop fallback: {e}")
   ```

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Pass the user query as HumanMessage | The query is already embedded in the SystemMessage via `VALIDATOR_SYSTEM_PROMPT.format(query=..., research_data=...)`. A fixed assessment instruction is cleaner and avoids repeating the user query in two turns. |
| Only fix auth error propagation, leave invoke as-is | Leaves the `BadRequestError` bug in place — LLM path would still silently fall to mock on every real call. |
| Remove the mock fallback entirely | Mock fallback is required for offline/CI operation where no API key is present. |

## Consequences

### Positive
- Validator's LLM path now works correctly with the OpenAI structured output endpoint
- `AuthenticationError` surfaces to the caller instead of being masked by the mock fallback
- Error handling pattern is now consistent across all three agents (clarity, research, validator)

### Negative / Trade-offs
- The fixed `HumanMessage` string is hardcoded — if the validation prompt is heavily refactored, this string may need updating to stay contextually accurate. Low risk at current scope.

### Files Affected
- `app/agents/validator_agent.py` — add HumanMessage to invoke, split except handler

## Related

- Bug #4 from plan.md
- Tests: `test_validator_agent_llm_invoke_includes_human_message`, `test_validator_agent_propagates_auth_error`
- Mirror pattern: `clarity_agent.py`, `research_agent.py` (same auth-error re-raise approach)
