# ADR-006: Synthesis Agent Prompt Security Boundary

**Date:** 2026-05-11
**Status:** Accepted
**Decider:** Claude Code session — Phase 5 (reviewer findings) / SECURITY HIGH

## Context

The original `SYNTHESIS_SYSTEM_PROMPT` embedded both the static instruction set AND the full Tavily research data in a single `SystemMessage`:

```
User Query/Topic: {query}
Raw Research Data:
{research_data}
```

This had two security problems:

1. **Prompt injection at system level**: Tavily results (external, untrusted content) were given the full authority of the system message — the same trust level as the agent's own instructions. A poisoned Tavily result containing `"Ignore all prior instructions..."` would be processed at system prompt authority.

2. **Python `.format()` injection**: `latest_query` and `research_str` were passed to `.format()` with no escaping. A user query containing `{` or `}` (e.g. `"What is {ROI}?"`) would cause a `KeyError` at runtime, crashing the agent.

Confirmed failing test: `test_synthesis_llm_path_sends_research_data_as_human_message` [RED → GREEN]

## Decision

Split the prompt into two messages:

1. **`SYNTHESIS_SYSTEM_PROMPT`** — static instructions only, contains only `{query}` (the user's search topic). User query is sanitized before `.format()` by replacing `{` → `{{` and `}` → `}}`.

2. **`SYNTHESIS_HUMAN_PROMPT`** — contains the research data block, delimited by `<research_data>` XML tags to signal to the model that this content is external/untrusted. Passed as a `HumanMessage`.

The `<research_data>` delimiter approach follows OpenAI's own guidance for separating trusted instructions from untrusted external content.

Additionally, `_extract_quantitative_lines` now escapes `|` → `\|` in extracted text and source fields before inserting into markdown table cells, preventing Tavily content from injecting extra column separators.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Keep single SystemMessage, sanitize all content | Does not fix the trust-level issue; Tavily content still runs at system authority even if escaped |
| Remove research data from the prompt entirely | Research data IS the core input for synthesis — the LLM needs it |
| Use f-string instead of `.format()` | f-strings evaluate at parse time; would require restructuring the prompt as a function; no benefit over sanitized `.format()` |
| Replace `|` with Unicode fullwidth pipe `｜` | Visually identical in monospace but semantically misleading; `\|` is the canonical markdown escape |

## Consequences

### Positive
- Tavily content runs at user-message authority, not system authority — prompt injection from external sources is demoted
- `{}` in user queries no longer crash the agent
- `|` in Tavily content no longer breaks markdown table rendering
- Prompt structure is cleaner and easier to modify (instructions vs. data are separate files/constants)

### Negative / Trade-offs
- `SYNTHESIS_HUMAN_PROMPT` cannot be used with `.format(research_data=...)` if `research_str` itself contains `{` or `}` — these are not escaped before insertion. Acceptable because `research_str` is constructed from `r.get(...)` fields which are already string-safe, and the `<research_data>` tag block makes the boundary explicit to the model.

### Files Affected
- `app/prompts/synthesis_prompt.py` — split into `SYNTHESIS_SYSTEM_PROMPT` + `SYNTHESIS_HUMAN_PROMPT`
- `app/agents/synthesis_agent.py` — sanitize `safe_query`, use two-message invoke, escape `|` in table cells

## Related

- Reviewer finding: `[SEVERITY: HIGH][CATEGORY: SECURITY]` and `[SEVERITY: HIGH][CATEGORY: PROMPT]` — Phase 5 review
- Tests: `test_synthesis_llm_path_sends_research_data_as_human_message`, `test_synthesis_agent_handles_format_braces_in_query`, `test_synthesis_agent_handles_pipe_in_research_content`
- Phase 8 will add delimiter tests for `research_prompt.py` and `validator_prompt.py` (same pattern)
