# Steward Platform ADRs

**Purpose:** Architecture Decision Records for the steward platform governing plan. Filed at Phase 0 kickoff per draft 8 §14 Open Items #11–#17 and updated as decisions evolve across phases.

**Naming convention:** `NNN-<slug>.md` for numbered ADRs; `BN-<slug>.md` for B-sub-deliverable ADRs (matches draft 8 §5-B sub-deliverables table).

**Seed source:** Plugin ADRs (005, B8, 007, 010) are seeded from analyst-a's source evaluation at `plans/steward_platform/plugin_source_evaluation.md` §6. Analyst-a source-read the actual plugins, found material marketing-vs-source discrepancies for three of four candidates, and produced source-grounded adoption decisions. The seeds below are the promotable ADR forms of those decisions.

**Lifecycle:** ADRs are immutable once filed. If a decision changes, a new ADR supersedes the old one with an explicit reference.

## Index

| ID | Title | Status | Primitive |
|---|---|---|---|
| 001 | Platform-11/13 dismissal evidence + agent-readability scorecard floor | Pending (Phase 0 kickoff) | C |
| 002 | Review-cycle-as-evidence (drafts 1–8 lineage) | Pending (Phase 0 close per analyst-d Q5) | C |
| 003 | Token-economy native vs. bespoke boundary | Pending (Phase 0 close) | F |
| 004 | Hook migration boundary | Pending (Phase 0 close) | E |
| **005** | **Review plugin evaluation** | **Seeded (draft 8)** | **C/E** |
| 006 | Auto mode codification | Pending (Phase 0 kickoff) | G |
| **007** | **Observability plugin evaluation** | **Seeded (draft 8)** | **A** |
| **010** | **mcp-memory-service evaluation** | **Seeded (draft 8)** | **C/D** |
| **B8** | **Native task/dependency system evaluation** | **Seeded (draft 8)** | **B** |
| G10 | `.claude/system_prompts/` vs. `.claude/agents/` relationship | Pending (Phase 0 kickoff; options: replacement/supplement/orthogonal) | G |

**Seeded** = draft 8 contains ADR seed text; the ADR file below is promotion-ready pending Phase 0 kickoff finalization (operator signoff + filing date).
