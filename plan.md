# ResearchFlow AI — Implementation Plan

## Problem Statement

Build a LangGraph multi-agent research assistant that collects business data for users, supports follow-up questions, and prompts for clarification on ambiguous queries.

## Architecture

Four specialized agents coordinated by a LangGraph state machine:

```
START → Clarity → Research → Validator (loop if needed) → Synthesis → END
```

Full graph topology and state schema documented in [.claude/commons/architecture-overview.md](.claude/commons/architecture-overview.md).

---

## Confirmed Bugs in Starter Code

| # | File | Lines | Bug |
|---|---|---|---|
| 1 | `research_agent.py` | 59 | Dead variable `structured_llm_or_fallback` in chained assignment |
| 2 | `clarity_agent.py` | 62–72 | Mock fallback only recognizes 7 hardcoded companies |
| 3 | `research_agent.py` | 23 | `validator_feedback` silently dropped in mock path |
| 4 | `validator_agent.py` | 45 | `invoke([system_msg])` missing required `HumanMessage` |
| 5 | `synthesis_agent.py` | 58–97, 112–128 | Hardcoded financial tables + boilerplate SWOT |
| 6 | `main.py` | 31 | `thread_id` hardcoded — sessions collide |
| 7 | `research_agent.py` | 44 | No URL deduplication on retry — list grows unboundedly |
| 8 | `tests/test_graph.py` | all | Only 3 happy-path tests |
| 9 | All agents | various | Silent exception swallowing hides real failures |

---

## TDD Phase Plan

Each phase: write failing tests first → confirm RED → implement → confirm GREEN → run reviewer.

### Phase 0 — .claude Infrastructure (complete)
Creates `.claude/rules/`, `.claude/skills/`, `.claude/commons/` with all documentation files. No Python changes.

### Phase 1 — State Schema + Conftest
**Tests:** `test_state_schema_has_required_fields`, `test_state_fields_have_correct_types`, `test_empty_initial_state_defaults_are_safe`
**Files:** `app/schemas/state.py`, `tests/conftest.py`
**ADR (conditional):** ADR-000 if reviewer recommends `Literal` types

### Phase 2 — Clarity Agent (Bug #2)
**Tests (RED):** `test_clarity_agent_clears_for_unlisted_company` (Salesforce — fails today), + 4 more
**Fix:** Replace 7-keyword list with proper-noun heuristic in mock fallback
**Files:** `app/agents/clarity_agent.py`
**ADR:** ADR-002

### Phase 3 — Research Agent (Bugs #1, #3, #7)
- **3a:** Remove dead variable — `refactor` commit, no new behavior
- **3b:** Test + fix feedback incorporation in mock path
- **3c:** Test + fix URL deduplication
**Files:** `app/agents/research_agent.py`
**ADR:** ADR-003

### Phase 4 — Validator Agent (Bug #4)
**Tests (RED):** `test_validator_agent_returns_validation_result_field` + 3 more
**Fix:** Add `HumanMessage` to `structured_llm.invoke()` call
**Files:** `app/agents/validator_agent.py`
**ADR:** ADR-001

### Phase 5 — Synthesis Agent (Bug #5)
**Tests (RED):** `test_synthesis_agent_does_not_contain_hardcoded_microsoft_figures` (fails today), + 4 more
**Fix:** Delete hardcoded table blocks and static SWOT; derive from `research_data`
**Files:** `app/agents/synthesis_agent.py`
**ADR:** ADR-004

### Phase 6 — main.py thread_id (Bug #6)
**Tests (RED):** `test_two_graph_sessions_with_different_thread_ids_are_independent`
**Fix:** `import uuid`, generate `str(uuid.uuid4())` per session
**Files:** `main.py`
**ADR:** ADR-005

### Phase 7 — Integration Edge Cases (no new implementation)
9 additional tests: empty/whitespace queries, Salesforce end-to-end, max_attempts boundary, dedup end-to-end, feedback flow end-to-end, confidence threshold boundary at 6, no boilerplate SWOT.

### Phase 8 — Prompt Injection Delimiters
**Tests (RED):** Assert delimiter patterns around `{query}` and `{research_data}` in all prompts
**Fix:** Wrap user-controlled content in `"""` or `<user_input>` XML tags
**Files:** `app/prompts/research_prompt.py`, `validator_prompt.py`, `synthesis_prompt.py`

### Phase 9 — Full Review + Docs
Run `langgraph-assistant-reviewer` on entire codebase. Address all CRITICAL/HIGH findings. Update `CLAUDE.md` and `architecture-overview.md`.

---

## Test Count Targets

| After Phase | Total Tests |
|---|---|
| Start | 3 |
| Phase 1 | 6 |
| Phase 2 | 11 |
| Phase 3 | 17 |
| Phase 4 | 21 |
| Phase 5 | 26 |
| Phase 6 | 27 |
| Phase 7 | 36 |
| Phase 8 | 39 |

---

## Pre-Identified ADRs

| ADR | Phase | Decision |
|---|---|---|
| ADR-000 (conditional) | 1 | Literal types for routing state fields |
| ADR-001 | 4 | Validator agent requires HumanMessage in invoke call |
| ADR-002 | 2 | Clarity fallback subject detection strategy |
| ADR-003 | 3c | Research data deduplication by URL |
| ADR-004 | 5 | Synthesis fallback derives content from research_data |
| ADR-005 | 6 | Thread ID generated as UUID4 per session |

---

## Verification

```bash
.venv/bin/python -m pytest tests/ -v
# Expected after Phase 9: ≥ 39 PASSED, 0 FAILED
```

Final gate: `langgraph-assistant-reviewer` full codebase review must show 0 CRITICAL, 0 HIGH findings.
