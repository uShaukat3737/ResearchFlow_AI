# ADR-003: Research Data Deduplication Strategy

**Date:** 2026-05-11
**Status:** Accepted
**Decider:** Claude Code session — Phase 3c / Bug #7

## Context

`research_agent.py` line 44 used `updated_data = current_data + new_results` on every retry loop. On the second and third research attempts, Tavily (or the mock) may return the same URLs as the first attempt. The list then contains duplicate entries — same title, URL, and content appearing multiple times. This was confirmed by `test_research_data_deduplication_on_retry` (RED against original code).

The `MEMORY_LEAK` category finding from the reviewer (Phase 3) also flagged this: unbounded list growth degrades synthesis quality (repeated facts) and increases token count per LLM call.

## Decision

Deduplicate `research_data` by URL before appending new results:

```python
seen_urls = {r["url"] for r in current_data}
deduped_new = [r for r in new_results if r.get("url") not in seen_urls]
updated_data = current_data + deduped_new
```

URL is used as the deduplication key because:
- It is always present in both real Tavily results and mock data
- It is stable across retries (same article = same URL)
- It is cheap to compare (string equality)

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Deduplicate by title | Titles can be slightly different for the same article (e.g., truncation); URL is more stable |
| Deduplicate by content hash | Adds `hashlib` complexity; content can differ for the same URL due to truncation; no clear benefit at this scale |
| No deduplication (keep as-is) | Causes the synthesis agent to receive repeated facts, bloats token counts, and grows `research_data` without bound across retries |

## Consequences

### Positive
- `research_data` length is bounded by the number of distinct URLs across all search results
- Synthesis agent receives clean, non-redundant input
- Token cost for validator and synthesis LLM calls does not escalate across retry loops

### Negative / Trade-offs
- If two different articles happen to share a URL (URL reuse/redirect), only the first version is kept
- Slightly more code per retry path

### Files Affected
- `app/agents/research_agent.py` — replace list concat with URL-dedup logic

## Related

- Bug #7 from plan.md
- Reviewer finding: `[SEVERITY: HIGH][CATEGORY: MEMORY_LEAK]` — Phase 3
- Tests: `test_research_data_deduplication_on_retry`, `test_research_data_grows_on_fresh_results`
