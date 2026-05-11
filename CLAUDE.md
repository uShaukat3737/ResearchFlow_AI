# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests (must use venv python)
.venv/bin/python -m pytest tests/ -v

# Run a single test
.venv/bin/python -m pytest tests/test_graph.py::test_ambiguous_query_halts_for_clarification

# Run the app (interactive CLI)
.venv/bin/python main.py

# Install dependencies into venv
.venv/bin/pip install -r requirements.txt
```

> The IDE uses system Python — always prefix test and run commands with `.venv/bin/python -m` to pick up installed packages. IDE "Cannot find module" errors for `langchain_core`, `openai`, `httpx` etc. are false positives.

## Required Environment Variables

Set in `.env` (both optional — agents fall back to mock data when absent):

```
OPENAI_API_KEY=sk-...       # Used by all agents (gpt-4o-mini; synthesis uses gpt-4o)
TAVILY_API_KEY=tvly-...     # Used by the Research Agent for web search
```

Any key value containing `"your_"` or equal to `"placeholder"` is treated as absent and triggers mock fallback.

## Architecture

**LangGraph multi-agent pipeline** for AI-powered business research. A directed `StateGraph` with conditional routing passes a single `ResearchAssistantState` TypedDict through each agent node.

### Graph Flow

```
START → clarity_agent
            ├─ needs_clarification → END   (graph halts; CLI re-prompts user)
            └─ clear → research_agent
                          ├─ high_confidence (score ≥ 6 OR attempts ≥ 3) → synthesis_agent → END
                          └─ low_confidence → validator_agent
                                                  ├─ loop_back (insufficient, attempts < 3) → research_agent
                                                  └─ synthesize → synthesis_agent → END
```

The `attempts ≥ MAX_RESEARCH_ATTEMPTS (3)` circuit-breaker in `route_research` ensures the loop always terminates even if the validator never returns "sufficient".

### State Schema (`app/schemas/state.py`)

| Field | Type | Who writes | Purpose |
|---|---|---|---|
| `messages` | `Annotated[List[BaseMessage], add_messages]` | clarity, synthesis | Append-only message history |
| `clarity_status` | `Literal["clear","needs_clarification"]` | clarity_agent | Routes after clarity check |
| `confidence_score` | `int` (0–10) | research_agent | Routes after research (threshold 6) |
| `validation_result` | `Literal["sufficient","insufficient"]` | validator_agent | Routes after validation |
| `attempts` | `int` | research_agent | Loop counter for circuit-breaker |
| `validator_feedback` | `Optional[str]` | validator_agent | Injected into next search query |
| `research_data` | `List[Dict]` | research_agent | Accumulated deduplicated results |

### Agents (`app/agents/`)

Each agent is `run_*(state: ResearchAssistantState) -> dict` returning only updated fields.

| Agent | LLM | Output format | Mock fallback |
|---|---|---|---|
| `clarity_agent` | gpt-4o-mini | Structured `ClarityAnalysis` | `_has_named_subject()` heuristic |
| `research_agent` | gpt-4o-mini | Structured `ResearchEvaluation` | keyword confidence (microsoft/apple/nvidia → 8, else 5) |
| `validator_agent` | gpt-4o-mini | Structured `ValidationAnalysis` | insufficient at attempts ≤ 1, sufficient otherwise |
| `synthesis_agent` | gpt-4o (temp 0.3) | Free text | data-driven report from `research_data` |

### Key Design Decisions

- **Mock fallback**: All agents check `OPENAI_API_KEY` and fall back to deterministic offline logic. Tests run fully offline.
- **Auth errors re-raised**: `AuthenticationError` and `RateLimitError` are never swallowed — they propagate to the caller so the user knows the key is invalid. Only transient/unexpected failures use the fallback.
- **URL deduplication**: `research_data` is deduplicated by URL on every research attempt to prevent list growth across retries (ADR-003).
- **Prompt injection boundaries**: User-controlled content and Tavily results are delimited with XML tags (`<user_query>`, `<research_data>`) in all prompts. Research data is passed as `HumanMessage`, not `SystemMessage`, in the synthesis agent (ADR-006).
- **Thread ID**: Each CLI session generates a `uuid4()` thread ID to prevent state bleed across restarts (ADR-005).
- **Literal routing fields**: `clarity_status` and `validation_result` use `Literal[...]` types for exhaustiveness checking (ADR-000).

### `.claude/` Structure

```
.claude/
├── agents/langgraph-assistant-reviewer.md   # Reviewer agent definition
├── rules/                                    # tdd-mandate, error-handling-policy, commit-discipline, reviewer-trigger-protocol
├── skills/                                   # run-tests, fix-agent-bug, write-adr
└── commons/
    ├── architecture-overview.md
    ├── adr-template.md
    └── decisions/                            # ADR-000 through ADR-006
```

Invoke `langgraph-assistant-reviewer` after any change to `app/agents/`, `app/graph/`, `app/schemas/`, or `app/prompts/`. Resolve all CRITICAL/HIGH findings before moving to the next phase.

### TDD Mandate

Always write a failing test before any implementation. Run `.venv/bin/python -m pytest tests/` after every file change. Commit RED test before implementing the fix.

### Test Count

63 tests covering: state schema contracts, all 4 agent unit tests (including auth error propagation, mock fallback, edge cases), routing logic, integration end-to-end paths, thread isolation, and prompt security delimiters.
