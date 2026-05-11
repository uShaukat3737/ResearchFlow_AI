# Error Handling Policy — No Silent Swallowing

## Acceptable: External Service Failures

`except Exception as e: logger.warning(...) + mock_fallback` is only acceptable when the failure source is an **external service**:
- OpenAI API (network error, quota exceeded, invalid key)
- Tavily API (network error, rate limit, invalid key)

Even then, the agent must return a state dict that signals degraded mode so downstream nodes can detect it.

## Never Acceptable

- Swallowing logic errors (wrong variable type, missing state field, bad argument)
- Catching `Exception` when you mean to catch a specific exception class
- Using a fallback to hide a bug that would otherwise be obvious

## Docstring Requirement

Every function that uses a mock fallback must document it:

```python
def run_foo_agent(state: ResearchAssistantState) -> dict:
    """
    ...
    FALLBACK: returns mock data when OPENAI_API_KEY is absent or placeholder.
    """
```

## Stack Trace Policy

Stack traces must **never** reach the CLI user. `main.py` is the only place allowed to catch exceptions and format them for human display. Agent-level errors must propagate as:
- State field updates (`error_message`, `degraded_mode: True`)
- Re-raises that bubble up to `main.py`

## Silent Fallback Anti-Pattern (DO NOT DO)

```python
# BAD — hides whether the real API was called or not
try:
    result = llm.invoke(messages)
except Exception as e:
    logger.warning(f"LLM failed: {e}")
    result = mock_result()  # user never knows this happened
```

## Correct Pattern

```python
# GOOD — caller can detect degraded mode
try:
    result = llm.invoke(messages)
    return {"output": result.content, "used_mock": False}
except Exception as e:
    logger.warning(f"LLM failed (using mock fallback): {e}")
    return {"output": mock_result(), "used_mock": True}
```
