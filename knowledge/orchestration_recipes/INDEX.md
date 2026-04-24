# Orchestration recipes index

> Auto-generation target: per governing plan §5-C (Primitive C) a
> `scripts/internal/generate_kb_index.py` script will rebuild this
> file from the recipes directory contents. Until that script ships,
> this INDEX is hand-maintained; `agent_readability_lint.py check
> recipes` will fail if a non-archive, non-template recipe is missing
> from the list below.
>
> Each recipe captures a reusable orchestration pattern — context in
> which it emerged, the decision shape, observed outcome, reuse
> guidance, and downstream citations. Archivist (Primitive D) will
> propose new recipes from repeat-pattern detection in event streams.

## Active recipes

- [shape_then_execute_pattern11.md](shape_then_execute_pattern11.md)
  — two-packet decomposition of novel multi-file, multi-decision work
  into an analyst-authored shape and an author-executed implementation.
  Seed entry for Primitive B.11. Version `b11-recipe-shape-then-execute-v1.0`.

## Conventions

- Filenames: `<slug>.md` where `<slug>` matches the version identifier
  tail (`b11-recipe-<slug>-v<MAJOR>.<MINOR>`).
- Every recipe file has six H2 sections: `Version`, `Context`,
  `Decision`, `Observed outcome`, `Reuse guidance`, `Downstream citations`.
- `_template.md` is the blank schema for new recipes (lint-skipped).
- `_archive/` holds retired recipes (superseded or proven ineffective;
  never delete, for lineage).
- `_candidates/` (not yet populated) is the archivist staging area;
  operator promotes to the active directory or rejects.
