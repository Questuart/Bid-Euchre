# Notebook Boundary Rule

> Notebooks are exploratory tools, not sources of truth for decisions.

## Core Principle

Decision-critical analysis (metrics, rankings, adoption evaluations, gate inputs)
must be reproducible from committed artifacts + scripts alone. Notebook outputs
(`.ipynb` cell results) are gitignored and exist only locally after execution —
they are not valid primary sources for report claims or modeling decisions.

## What Counts as Decision-Critical

- Metrics cited in promotion reports, decision reports, or gate evaluations
- Rankings used to compare bidders or strategies
- Adoption/rejection criteria for protocol decisions (threshold, lambda, normalizer)
- Any number that, if wrong, would change a PROMOTED/HALT/RETAIN decision

## Required Traceability

Every decision-critical claim in a report must trace to one of:

1. **Committed JSON artifact** (e.g., `comparator_cis_r0_v6.json`)
2. **Report provenance section** with reproduction command and seed
3. **Script output** reproducible via `uv run python scripts/...` with documented seed

A notebook may *produce* the analysis, but the result must be *captured* in one
of the above committed forms before a report may cite it as decision evidence.

## Anti-Patterns

❌ Report cites a metric with no committed source — only visible in notebook output
❌ Decision gate (e.g., normalizer trigger) computed in notebook, never written to artifact
❌ Ephemeral config generated in notebook used for experiment but never committed
❌ Report says "See notebook S4 for exact counts" without recording the counts anywhere

## Acceptable Patterns

✅ Notebook computes bootstrap CIs → script extracts them into committed JSON artifact
✅ Report embeds the actual numbers (not just "see notebook") with a repro command
✅ Notebook explores parameter space → decision captured in protocol with repro command
✅ Notebook produces diagnostic charts that supplement (not replace) committed evidence
