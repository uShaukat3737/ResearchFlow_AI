# ADR-004: Synthesis Agent Data-Driven Fallback

**Date:** 2026-05-11
**Status:** Accepted
**Decider:** Claude Code session — Phase 5 / Bug #5

## Context

`synthesis_agent.py` contained three hardcoded financial tables (one each for Microsoft, Apple, NVIDIA) with specific revenue figures, EPS, and growth rates that were injected into the report regardless of what the `research_data` contained. A generic fourth branch injected a "Strategic AI Spending Metrics" table with fabricated industry averages.

The SWOT analysis section was identical for every company: the same four strengths, two weaknesses, two opportunities, and two threats appeared in all reports. None of this content was derived from retrieved research data.

Confirmed failing tests:
- `test_synthesis_agent_does_not_contain_hardcoded_microsoft_figures` [RED → GREEN]
- `test_synthesis_agent_outputs_data_gap_notice_when_no_research_data` [RED → GREEN]
- `test_synthesis_agent_produces_output_without_generic_boilerplate_swot` [RED → GREEN]

## Decision

Replace the hardcoded table and SWOT blocks with two data-driven helpers:

1. **`_extract_quantitative_lines(research_data)`** — scans each result's `content` field for sentences containing financial signals (`$`, `%`, `billion`, `million`, `trillion`). Returns up to 10 rows for a markdown table. If nothing is found, the section reads "No quantitative data retrieved from search results."

2. **`_format_sources(research_data)`** — renders a numbered markdown list of source titles and URLs. Returns "_No sources retrieved._" when the list is empty.

The boilerplate SWOT section is removed entirely. If the user wants strategic analysis, the LLM path (with a real API key) handles it through `SYNTHESIS_SYSTEM_PROMPT`.

Also added `AuthenticationError`/`RateLimitError` re-raise (same pattern as other agents), and removed the `SystemMessage`-only LLM invocation guard (synthesis uses a single `SystemMessage` which is valid for GPT-4o in chat completion mode).

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Keep hardcoded tables but expand to more companies | Does not scale; every new company requires a code change; tables fabricate data not present in research results |
| LLM-generated SWOT in mock path using a second LLM call | Requires API key — defeats the purpose of the mock fallback |
| Keyword-scan SWOT (extract strength/weakness keywords from research_data) | Adds complexity for uncertain value; removed section is cleaner and more honest |
| Keep generic "AI Spending Metrics" else branch | Injects fabricated data for any non-Microsoft/Apple/NVIDIA company — same root problem |

## Consequences

### Positive
- Report content is now 100% derived from actual `research_data` — no fabricated figures
- Works for any company name, not just three hardcoded ones
- When research data is empty, the report honestly signals the data gap instead of hiding it
- `_extract_quantitative_lines` and `_format_sources` are independently testable helpers

### Negative / Trade-offs
- Mock-path reports are less visually rich than the hardcoded tables (no pre-formatted financial statement layout). This is acceptable — the LLM path produces rich output; the mock path is for CI/offline operation.
- Quantitative extraction uses regex sentence splitting which may split mid-number on commas (e.g., "Revenue of $1,234.5 million" split at ","  is handled by the pattern matching the full token before the comma).

### Files Affected
- `app/agents/synthesis_agent.py` — remove hardcoded blocks, add two helper functions, add auth error re-raise

## Related

- Bug #5 from plan.md
- Tests: `test_synthesis_agent_does_not_contain_hardcoded_microsoft_figures`, `test_synthesis_agent_outputs_data_gap_notice_when_no_research_data`, `test_synthesis_agent_produces_output_without_generic_boilerplate_swot`, `test_synthesis_agent_derives_content_from_research_data`, `test_synthesis_agent_includes_source_links_from_research_data`, `test_synthesis_agent_produces_output_for_any_company`
