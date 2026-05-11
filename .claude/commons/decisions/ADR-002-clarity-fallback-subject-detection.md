# ADR-002: Clarity Agent Fallback Subject Detection Strategy

**Date:** 2026-05-11
**Status:** Accepted
**Decider:** Claude Code session — Phase 2 / Bug #2

## Context

The clarity agent mock fallback (used when no OpenAI API key is present) only recognised 7 hardcoded company names:
`["microsoft", "apple", "nvidia", "google", "meta", "tesla", "amazon"]`

Any company not in this list — including well-known names like "Salesforce", "Palantir", "IBM" — received `needs_clarification`, silently blocking the research pipeline. This made the mock fallback unusable for realistic demos and made tests fragile (tests were coupled to the hardcoded list).

Confirmed by: `test_clarity_agent_clears_for_unlisted_company` (RED against current code).

## Decision

Replace the hardcoded list with a **sentence-opener exclusion heuristic**:

1. Tokenise all messages in history (not just the latest)
2. For each word token, strip trailing punctuation
3. If the token starts with an uppercase letter AND its lowercase form is NOT in the common English sentence-opener set, treat it as a named subject → `"clear"`
4. If no such token is found across all messages → `"needs_clarification"`

**Common sentence-opener set (excluded from subject detection):**
```python
SENTENCE_OPENERS = {
    "what", "how", "when", "where", "why", "who", "which",
    "tell", "show", "explain", "provide", "analyze", "give",
    "find", "can", "could", "is", "are", "do", "does", "did",
    "has", "have", "get", "please", "i", "the", "a", "an",
}
```

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Expand hardcoded list | Does not scale; will always be incomplete; requires code change for every new company |
| LLM-only (no fallback) | Tests run without API keys — offline operation is a requirement |
| Keep list + add Salesforce | Patch, not fix; list will break again for the next missing company |
| Regex for ticker symbols or proper nouns | More complex; `re` adds import; not meaningfully better for this use case |

## Consequences

### Positive
- Mock fallback now recognises any capitalised proper noun (Salesforce, Palantir, Roche, etc.)
- Tests are no longer coupled to a specific 7-company enumeration
- Context resolution still works: checks all message history, not just the latest

### Negative / Trade-offs
- Heuristic can produce false positives: a query like `"What is Q3 data?"` would detect `"Q3"` as a named subject (starts uppercase, not in opener set). This is acceptable for a demo mock — the real LLM path handles ambiguity correctly.
- Heuristic does not perform true NER (Named Entity Recognition); it is intentionally simple

### Files Affected
- `app/agents/clarity_agent.py` — replace hardcoded list with heuristic function

## Related

- Bug #2 from plan.md
- Tests: `test_clarity_agent_clears_for_unlisted_company`, `test_clarity_agent_resolves_pronoun_from_history`
- Reviewer Step 8 (Missing Edge Cases): whitespace-only content, empty messages
