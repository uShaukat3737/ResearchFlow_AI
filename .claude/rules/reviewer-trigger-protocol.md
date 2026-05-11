# langgraph-assistant-reviewer Invocation Protocol

## When to Invoke

Invoke the `langgraph-assistant-reviewer` agent automatically after any phase that modifies or creates files in:

- `app/agents/` — any agent file
- `app/graph/builder.py` or `app/graph/routing.py`
- `app/schemas/state.py`
- `app/memory/checkpoint.py`
- `app/prompts/` — any prompt file

## Rules

1. **Same-phase resolution**: Reviewer findings must be addressed within the same phase before advancing. No carry-forward of unresolved findings.

2. **ADR gate**: Any reviewer finding that changes a design decision (e.g., "use HumanMessage not SystemMessage alone", "add deduplication key", "use Literal types") requires an ADR written in `.claude/commons/decisions/` before the fix is committed.

3. **Code-quality findings** (formatting, naming, dead code): Fix and move on — no ADR needed.

4. **CRITICAL or HIGH findings**: The phase is not complete until a new green test covering that issue exists.

5. **LOW and INFO findings**: Document in the reviewer's agent memory. Fix if trivial; otherwise log in `.claude/commons/decisions/` as a known trade-off.

## How to Invoke

Use the `langgraph-assistant-reviewer` agent with the modified file paths as context. For a full-codebase review (Phase 9), invoke with: "Full codebase review. All files."
