# Agentic Orchestration Platform — Amendments

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Last updated:** 2026-03-20

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

---

## A2 — Front-load primary PR review architecture into Platform-3 (2026-03-20)

**PR:** #1180 (docs: front-load primary PR review architecture)

**What changed:**
1. **Platform-3 scope expanded** — Platform-3 now owns the primary PR review
   architecture: durable review request/verdict state (extending the
   `ReviewRequest`/`ReviewVerdict` models from #1176) and a merge-safety gate
   driven by verdict state rather than hook-coupled subprocess parsing.
   Platform-3 renamed from "Communication Bus V1" to "Communication Bus V1
   And Primary PR Review Substrate." A new sub-slice `Platform-3d` covers
   review request/verdict state and the merge-safety gate.
2. **Platform-12 reframed** — Platform-12 (Cross-Model Review And Maintenance)
   is now explicitly an extension of Platform-3's review substrate. Second-model
   findings are recorded as verdicts in the Platform-3 review bus, not as a
   separate review truth model. Platform-12 does not redefine the review
   architecture; it adds cross-model execution as a consumer.
3. **SendMessage deferral** — `SendMessage`-style lane-to-lane delivery is
   explicitly deferred as a convenience layer on top of the durable review
   bus. It is not the source of review truth.
4. **Batch B pass gate updated** — Added a review-substrate acceptance
   criterion: one real PR review request stored durably as a `ReviewRequest`,
   receiving a `ReviewVerdict`, driving merge-safety state without subprocess
   parsing.
5. **Instrumentation** — Platform-3 instrumentation gains review request →
   verdict latency and merge-safety gate accuracy metrics.

**Rationale:** The review substrate should ship early so all downstream slices
(dashboard, supervisor, cross-model review) build on durable review state from
the start. Deferring the primary review architecture to Platform-12 would
force interim work to rely on hook-coupled subprocess parsing and transient
terminal output — the exact failure mode the platform is designed to replace.
