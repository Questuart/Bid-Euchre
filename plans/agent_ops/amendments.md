# Agentic Orchestration Platform — Amendments

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Last updated:** 2026-03-21

---

## A1 — Platform-1 entry criteria and filesystem boundary (2026-03-20)

**PR:** #1090 (docs: gate Platform-1 on review-surface stabilization)

**What changed:**
1. **Platform-1 entry criteria** — Added two new entry criteria:
   - Review-surface stability (reviewing-changes advisory status settled,
     claude-review visible without poisoning CI, Codex Cloud behavior recorded)
   - Repo-bounded filesystem access (default deny for external paths)
2. **Filesystem access boundary** — New subsection under Security/Safety
   defining repo-bounded filesystem access as the default, with explicit
   exception + audit path for outside-repo access.
3. **Platform-12 rewrite** — "Interim advisory CI path" renamed to "Interim
   Codex overlay path." Constraints updated to reflect that Codex Cloud
   delivers findings as PR issue comments (not checks/statuses), and that
   the comment-ingestion bridge is the integration mechanism.

**Rationale:** Codex Cloud proving-run findings (2026-03-20) revealed that
Codex Cloud does not produce check runs, commit statuses, or PR review
objects. The filesystem access boundary was added based on operational
experience with autonomous agents accessing paths outside the repo tree.
