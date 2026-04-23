# ADR 010 — mcp-memory-service Evaluation

**Status:** SEEDED (draft 8); filing at Phase 0 kickoff
**Primitive:** C (durable memory + KB), D (archivist inflow/outflow)
**Supersedes:** none
**Seed source:** `plans/steward_platform/plugin_source_evaluation.md` §5 + §6.4 (analyst-a, 2026-04-23)

---

## Context

`doobidoo/mcp-memory-service` (Apache-2.0, v10.13.0, 1717 stars at time of evaluation) provides MCP tools for semantic memory (`store_memory` / `retrieve_memory` / `search_by_tag` / `delete_memory` / `list_memories` / `recall_memory` / etc.), plus autonomous "dream-inspired" consolidation (exponential decay scoring, creative association discovery, semantic compression, controlled forgetting) and pluggable storage backends (SQLite-vec / Cloudflare KV+Vectorize / Milvus / Hybrid local+cloud).

Source read (2026-04-23 by analyst-a) exposes multiple impedance mismatches with steward's Primitive C/D discipline:

- **All §9.7 first-class IDs absent** from the memory schema. Would have to live inside `metadata: Optional[Dict[str, Any]]`, making them non-queryable except via full-scan. Impedance is deeper than ID mapping: the plugin models memory as "content + tags + semantic embedding"; steward models knowledge as "curated artifact classes (NOTES / PLAYBOOKS / anti_patterns / incidents / ADRs / harness_assumptions / INDEX)" with explicit operator-gated promotion.
- **Storage lives outside git.** Per-machine SQLite, Cloudflare KV, Milvus — none write to git-committed markdown. Conflicts with `.claude/rules/deferred/30_data_contract.md` commit policy ("only promoted artifacts committed") and with draft 8's KB structure (committed markdown under `knowledge/`).
- **Autonomous consolidation silently mutates memory state.** `ControlledForgettingEngine` deletes low-importance memories after a configurable window; `SemanticCompressionEngine` compresses clusters into summary entries; `DreamInspiredConsolidator` orchestrates both. Conflicts with draft 8's explicit-promotion + operator-review-gate discipline (Primitive D archivist inflow is operator-reviewed; GC outflow is operator-accepted; there is no "silently mutate state" path).
- **Heavy dependency footprint.** ChromaDB / SQLite-vec / Cloudflare — introduces infrastructure not justified by a current steward workflow.

The plugin's value is the semantic retrieval layer. Steward does not currently have a semantic-retrieval workflow; grep over curated markdown satisfies the current use case.

## Decision

**Do not adopt.** Keep `ops/memory.py` + `knowledge/` curated markdown + MEMORY.md + archivist operator-gated promotion as the Primitive C/D mechanism.

**Reference the plugin's MCP tool signatures only** — if steward later exposes an MCP interface over the committed KB corpus (unlikely until Phase 2+), reuse the shape (`store_memory` / `retrieve_memory` / `search_by_tag` / `list_memories` / `delete_memory` + `destructiveHint` / `readOnlyHint` MCP tool annotations).

## Consequences

- Steward's commit discipline (only promoted artifacts committed; operator review before promotion) remains intact.
- No vector-DB dependency introduced.
- KB stays git-auditable and portable.
- Archivist flow stays operator-gated — no autonomous state mutation.
- **Phase 3 soft re-evaluation trigger:** revisit if either fires during Phase 1/2:
  - (a) `knowledge/NOTES.md` exceeds a size where grep-based recall breaks agent-readability — soft threshold: ~20 KB or ~500 entries, whichever first.
  - (b) Archivist inflow volume exceeds operator-review capacity — ≥10 candidate lessons per nightly run sustained for ≥1 week.
- Recommended evaluation window: 6 months post Phase 2 close.

## Alternatives considered

1. **Wholesale adoption as replacement for `ops/memory.py`.** Rejected. Autonomous consolidation conflicts with commit discipline; heavy dependency footprint; lock-in via content-hash + embedding storage; §9.7 IDs not first-class.
2. **Adopt as supplemental inflow-only layer.** Deferred. No current workflow requires semantic retrieval; re-evaluate at Phase 3 trigger.
3. **Stand up a thin `sentence-transformers + SQLite-vec` wrapper over the committed markdown corpus.** Deferred. Cheaper than adopting the plugin, but only if a semantic-retrieval need emerges; no current need.

## Open questions

1. Phase 3 soft re-evaluation trigger thresholds (~20 KB / 500 entries / 10 candidate lessons per nightly / 1 week sustained) are first-cut. Operator can calibrate against actual KB growth observed during Phase 0. Alternative: "grep produces >50 hits on a common query" as an operator-readable threshold.

## Source evidence

- Plugin repo: `https://github.com/doobidoo/mcp-memory-service`
- License: Apache-2.0; v10.13.0
- Source-read modules: `storage/sqlite_vec.py` (192 KB), `server_impl.py` (152 KB), `consolidation/__init__.py` + associated modules (`decay.py`, `associations.py`, `clustering.py`, `compression.py`, `forgetting.py`, `consolidator.py`, `scheduler.py`, `health.py`), `storage/graph.py` + `consolidation/relationship_inference.py` (27 KB each).
- Evaluation artifact: `plans/steward_platform/plugin_source_evaluation.md` §5 (analyst-a, 2026-04-23)

## Phase 2 Decision Inputs

**Portability readiness:** Improved. Rejection keeps `ops/memory.py` + `knowledge/` markdown as the portable pattern.
**Meta-layer need:** no change.
**Kill signal for primitive(s) named:** no. Primitive C (durable memory + KB) + Primitive D (archivist) remain live; ADR 010 closes a named evaluation without reshaping scope.
**Re-evaluation needed in Phase 3:** **Yes, soft trigger.** Revisit if thresholds in §Consequences fire during Phase 1/2.
**Surprise finding:** Plugin storage layer is larger than the rest of the plugin combined (192 KB `sqlite_vec.py` vs. 27 KB `graph.py` + 152 KB `server_impl.py`). Most of the cost is in backend + embeddings, not the MCP interface. If steward ever did need semantic retrieval, a thin `sentence-transformers + SQLite-vec` wrapper over committed markdown would be cheaper than adopting this plugin.
**Disposition:** open (pending Phase 0 kickoff filing)
