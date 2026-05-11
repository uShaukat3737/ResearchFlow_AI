# ResearchFlow AI — Architecture Overview

**Last updated:** 2026-05-11 (post Phase 9 rebuild)

## System Purpose

AI-powered business research assistant. A user submits a query about a company; the pipeline clarifies ambiguity, searches the web for data, validates data quality, and synthesizes a structured Markdown business report.

---

## Agent Inventory

| Agent | Function | Model | Temp | Structured Output | State Fields Written |
|---|---|---|---|---|---|
| Clarity | `run_clarity_agent` | gpt-4o-mini | 0 | `ClarityAnalysis` | `clarity_status`, `messages` |
| Research | `run_research_agent` | gpt-4o-mini | 0 | `ResearchEvaluation` | `research_data`, `attempts`, `confidence_score` |
| Validator | `run_validator_agent` | gpt-4o-mini | 0 | `ValidationAnalysis` | `validation_result`, `validator_feedback` |
| Synthesis | `run_synthesis_agent` | gpt-4o | 0.3 | None (free text) | `messages` |

---

## Graph Topology

```
START
  └─► clarity_agent
          ├─[needs_clarification]─► END  (user must reply; graph pauses)
          └─[clear]─► research_agent
                          ├─[high_confidence: score ≥ 6 OR attempts ≥ MAX_RESEARCH_ATTEMPTS]─► synthesis_agent ─► END
                          └─[low_confidence]─► validator_agent
                                                   ├─[loop_back: insufficient AND attempts < MAX_RESEARCH_ATTEMPTS]─► research_agent
                                                   └─[synthesize: sufficient OR attempts ≥ MAX_RESEARCH_ATTEMPTS]─► synthesis_agent ─► END
```

**Router functions** (`app/graph/routing.py`):
- `route_clarity` — reads `clarity_status`
- `route_research` — reads `confidence_score` AND `attempts`; threshold ≥ 6 or circuit-breaker `attempts ≥ MAX_RESEARCH_ATTEMPTS (3)`
- `route_validator` — reads `validation_result` and `attempts`; uses `MAX_RESEARCH_ATTEMPTS` constant (not a magic number)

**Circuit-breaker**: `research_agent` returns early with `confidence_score=0` when `attempts >= MAX_ATTEMPTS`. `route_research` then routes to synthesis directly, bypassing the validator — preventing a 4th unnecessary validator invocation.

---

## State Schema (`app/schemas/state.py`)

`ResearchAssistantState` — LangGraph `TypedDict`

| Field | Type | Written by | Read by | Role |
|---|---|---|---|---|
| `messages` | `Annotated[List[BaseMessage], add_messages]` | Clarity, Synthesis | All agents | Full conversation history; `add_messages` reducer appends (never overwrites) |
| `clarity_status` | `Literal["clear","needs_clarification"]` | Clarity | `route_clarity` | Routing signal (ADR-000: Literal type) |
| `confidence_score` | `int` | Research | `route_research` | 0–10; threshold ≥ 6 for fast path |
| `validation_result` | `Literal["sufficient","insufficient"]` | Validator | `route_validator` | Routing signal (ADR-000: Literal type) |
| `research_data` | `List[Dict[str, Any]]` | Research | Validator, Synthesis | Accumulated results; URL-deduplicated (ADR-003) |
| `attempts` | `int` | Research | `route_research`, `route_validator` | Loop counter; MAX_RESEARCH_ATTEMPTS = 3 |
| `validator_feedback` | `Optional[str]` | Validator | Research | Gap-filling instructions; `None` when sufficient; never silently dropped (Bug #3 fix) |

---

## Mock Fallback System

All agents and the search tool check API key validity with:
```python
if api_key and "your_" not in api_key and api_key != "placeholder":
    # real LLM/API call
else:
    # deterministic mock fallback
```

**Mock behaviors (post-rebuild):**
- **Clarity**: `_has_named_subject()` heuristic — any capitalized token not in `_SENTENCE_OPENERS` set is treated as a valid subject. Handles any company name, not just 7 hardcoded ones (ADR-002).
- **Research**: Microsoft/Apple/NVIDIA keywords → confidence 8; others → confidence 5. Feedback is appended to the search query string in mock mode (Bug #3 fix).
- **Validator**: returns `"insufficient"` at attempts ≤ 1, `"sufficient"` at attempts ≥ 2. Always returns explicit `validator_feedback: None` when sufficient.
- **Synthesis**: builds a data-driven report from actual `research_data` content. No hardcoded financial tables or boilerplate SWOT (ADR-004). `_extract_quantitative_lines()` scans for `$`, `%`, `billion/million` patterns.
- **Tavily**: returns static mock results for Microsoft, Apple, NVIDIA; generic 2-result mock for all others.

---

## Error Handling Policy

- `AuthenticationError` and `RateLimitError` are **always re-raised** in all four agents — never swallowed.
- Only `except Exception` (transient/unexpected failures) triggers mock fallback, with `logger.warning()` — never silent `pass`.
- Stack traces never reach CLI output.

---

## Prompt Security

All user-controlled content and external (Tavily) data is delimited with XML tags in prompts (ADR-006):
- `<user_query>`, `<validator_feedback>`, `<search_results>` in research prompts
- `<user_query>`, `<research_data>` in validator prompt
- Research data passed as `HumanMessage` (user-level authority) not `SystemMessage` in synthesis agent
- `{` and `}` in user queries and research strings are escaped before `.format()` calls

---

## Known Design Constraints

- **MemorySaver is in-memory only** — all session state is lost when the process exits. Suitable for CLI demo; not for production. Upgrade path: swap `MemorySaver` for `AsyncPostgresCheckpointer`.
- **Thread ID** is `uuid4()` per process run (ADR-005). Sessions do not persist across restarts.
- **No rate limiting** — the CLI does not limit query rate.
- **Synthesis uses gpt-4o** at temperature 0.3 vs gpt-4o-mini at 0 for all other agents.
- **`add_messages` reducer** means `messages` grows without bound within a session. No windowing.
- **Mock confidence** only scores 3 companies at 8 — all others score 5, forcing the validator loop path. This is intentional for demo purposes.

---

## ADR Index

| ADR | Decision | Phase |
|---|---|---|
| ADR-000 | `Literal[...]` types for `clarity_status` and `validation_result` | Phase 1 |
| ADR-001 | Validator `invoke` must include a `HumanMessage` | Phase 4 |
| ADR-002 | Clarity fallback uses sentence-opener exclusion heuristic | Phase 2 |
| ADR-003 | Research data deduplication by URL | Phase 3c |
| ADR-004 | Synthesis data-driven fallback (no hardcoded tables/SWOT) | Phase 5 |
| ADR-005 | Thread ID generated as `uuid4()` per session | Phase 6 |
| ADR-006 | Synthesis prompt security boundary (XML tags, HumanMessage) | Phase 5 reviewer |
