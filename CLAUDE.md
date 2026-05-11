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

> The IDE uses system Python — always prefix test and run commands with `.venv/bin/python -m` to pick up installed packages. IDE "Cannot find module" errors for `langchain_core`, `langchain_google_genai`, `google.genai` etc. are false positives.

## Required Environment Variables

Set in `.env` (optional — agents fall back to mock data when absent):

```
OPENAI_API_KEY=sk-proj-...   # Used by default (gpt-4o-mini; synthesis uses gpt-4o)
ANTHROPIC_API_KEY=sk-ant-... # Alternative provider (claude-3-5-haiku; synthesis uses claude-3-5-sonnet)
GEMINI_API_KEY=AIza...       # Alternative provider (gemini-2.0-flash)
TAVILY_API_KEY=tvly-...      # Used by the Research Agent for web search
LLM_PROVIDER=openai          # Override provider selection (openai, anthropic, google)
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
                          ├─ low_confidence → validator_agent
                          │                       ├─ loop_back (insufficient, attempts < 3) → research_agent
                          │                       └─ synthesize → synthesis_agent → END
                          └─ degraded_mode (circuit breaker) ───────────→ synthesis_agent → END
```

The `attempts ≥ MAX_RESEARCH_ATTEMPTS (3)` circuit-breaker in `route_research` ensures the loop always terminates even if the validator never returns "sufficient".
An API-failure circuit breaker triggers if an unrecoverable LLM quota limit or auth error is encountered, shifting the state to `degraded_mode` and skipping directly to `synthesis_agent`.

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
| `degraded_mode` | `Optional[str]` | any agent | Signals unrecoverable quota/billing/auth limits |

### Agents (`app/agents/`)

Each agent is `run_*(state: ResearchAssistantState) -> dict` returning only updated fields.

| Agent | LLM | Output format | Mock fallback |
|---|---|---|---|
| `clarity_agent` | Dynamic Router | Structured `ClarityAnalysis` | `_has_named_subject()` heuristic |
| `research_agent` | Dynamic Router | Structured `ResearchEvaluation` | keyword confidence (microsoft/apple/nvidia → 8, else 5) |
| `validator_agent` | Dynamic Router | Structured `ValidationAnalysis` | insufficient at attempts ≤ 1, sufficient otherwise |
| `synthesis_agent` | Dynamic Router | Free text | data-driven report / degraded mode warning |

### Key Design Decisions

- **LLM Router**: Centralized in `app/utils/llm_router.py`. Automatically detects which API key is present (prioritizing OpenAI -> Anthropic -> Google) and instantiates the proper model with `.with_structured_output(...)` capabilities.
- **Mock fallback**: All agents fall back to deterministic offline logic if no API keys are detected. Tests run fully offline.
- **Unrecoverable Error Circuit Breaker**: If an unrecoverable API error (e.g. RateLimitError/AuthenticationError/ClientError) is raised, the agent catches it, classifies it via `classify_llm_error`, flags `degraded_mode` in the state, and short-circuits execution directly to `synthesis_agent`. The Synthesis Agent then prints `"Research unavailable due to LLM quota limits"` instead of generating fake report outputs.
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
