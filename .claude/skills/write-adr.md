# Skill: Write Architecture Decision Record

## Trigger

Use when the `langgraph-assistant-reviewer` or a code review identifies a finding that:
- Changes a design decision
- Introduces a new pattern that will be reused
- Rejects an existing approach in favor of a different one
- Resolves a known trade-off (e.g., performance vs correctness)

## Steps

1. **Determine next ADR number** — count files in `.claude/commons/decisions/` (excluding `.gitkeep`)
2. **Create the ADR file** at `.claude/commons/decisions/ADR-NNN-<kebab-case-title>.md`
3. **Fill using the template** from `.claude/commons/adr-template.md`:
   - Title, date (today), status: `Accepted`
   - Context: what situation or finding prompted this decision
   - Decision: what was chosen — reference exact files, function names, field names
   - Alternatives Considered: what else was evaluated and why rejected
   - Consequences: positive effects, negative trade-offs, files affected
   - Related: reviewer finding category, test names, other ADRs
4. **Commit the ADR standalone** before the implementation fix: `docs(adr): ADR-NNN <title>`
5. **Reference the ADR** in the implementation commit message: `fix(scope): description — see ADR-NNN`

## Naming Convention

```
ADR-001-validator-humanmessage-requirement.md
ADR-002-clarity-fallback-subject-detection.md
ADR-003-research-data-deduplication-strategy.md
```
