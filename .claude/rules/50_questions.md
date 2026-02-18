# Question-Asking Convention

> This rule governs how Claude asks planning and clarification questions during interactive sessions.

## Default: Use AskUserQuestion for Planning

When starting any non-trivial task, use structured questions to align on scope, approach, and tradeoffs **before writing code**.

Triggers for structured questions:
- Multiple valid implementation approaches exist
- Scope is ambiguous or could be interpreted broadly
- Architectural decisions affect future work
- The task touches >2 files or crosses module boundaries

## Recommendation-First Format

Every question **must** include a recommended option. Alternatives include concise tradeoffs grounded in repo evidence.

**Required per option:**
- 1–2 sentence tradeoff citing concrete evidence (existing patterns, doc constraints, prior decisions)
- Clear differentiation from the recommendation

**Evidence sources (in priority order):**
1. Existing code patterns in `src/bid_euchre/`
2. Constraints from `docs/01_core/` or `docs/02_agent/`
3. Prior PRs or decisions documented in MEMORY.md
4. General engineering tradeoffs (last resort)

## Text-Then-Widget Pattern

Structure every planning question in two phases:

1. **Markdown text output** — full context including:
   - Problem statement (what needs deciding)
   - Options with tradeoffs and evidence
   - Explicit recommendation with rationale

2. **AskUserQuestion widget** — concise selection only:
   - Short labels (1–5 words per option)
   - Brief descriptions (1 sentence max)
   - Recommended option marked with "(Recommended)" suffix
   - No substantive analysis in widget fields — that belongs in the text above

## Anti-Patterns

1. **Context buried in widget** — don't put tradeoff analysis in `description` fields; put it in the markdown text
2. **Options without recommendation** — never present choices as equally weighted; always take a position
3. **Recommendation without evidence** — cite repo patterns, doc constraints, or prior decisions; don't just assert preference
4. **Questions without context** — don't fire AskUserQuestion without preceding markdown explaining why the question matters
5. **Over-questioning** — don't ask when there's an obvious single approach consistent with repo conventions; just do it
