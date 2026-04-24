# Steward Platform ADRs (knowledge/adr/)

**Purpose:** Canonical Architecture Decision Records for the steward
platform. This is the promoted location under Primitive C's KB.
Pre-Phase-0 seeds lived at `plans/steward_platform/adrs/`; that
directory is now a redirect for entries migrated here.

**Naming convention:** `NNN-<slug>.md` for numbered ADRs;
`BN-<slug>.md` / `GN-<slug>.md` for sub-deliverable ADRs (matches
governing plan §5 sub-deliverable tables).

**Lifecycle:** ADRs are immutable once filed. If a decision changes, a
new ADR supersedes the old one with an explicit reference.

**Commit policy (ADR 010):** ADRs are tracked at this location. Pattern
7 rollback paths must be cited in the ADR body (supersession, revert
commit, or scope-dismiss path).

## Index

| ID | Title | Status | Primitive | Location |
|---|---|---|---|---|
| **001** | Platform Pattern Reset — Platform-11/13 dismissal + agent-readability scorecard floor (7/10) | Seeded (Phase 0 kickoff) | Meta (B / C / G) | [`001-platform-pattern-reset.md`](001-platform-pattern-reset.md) |
| 002 | Review-cycle-as-evidence (drafts 1–8 lineage) | Pending (Phase 0 close) | C | _pending promotion_ |
| 003 | Token-economy native vs. bespoke boundary | Pending (Phase 0 close) | F | _pending promotion_ |
| 004 | Hook migration boundary | Pending (Phase 0 close) | E | _pending promotion_ |
| 005 | Review plugin evaluation | Seeded at `plans/steward_platform/adrs/005-review-plugin-evaluation.md` | C / E | _pending promotion_ |
| 006 | Auto mode codification | Seeded at `plans/steward_platform/adrs/006-auto-mode.md` | Meta / G | _pending promotion_ |
| 007 | Observability plugin evaluation | Seeded at `plans/steward_platform/adrs/007-observability-plugin-evaluation.md` | A | _pending promotion_ |
| 010 | mcp-memory-service evaluation | Seeded at `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` | C / D | _pending promotion_ |
| B8 | Native task / dependency system evaluation | Seeded at `plans/steward_platform/adrs/B8-native-task-system-evaluation.md` | B | _pending promotion_ |
| G10 | `.claude/system_prompts/` vs. `.claude/agents/` relationship | Seeded at `plans/steward_platform/adrs/G10-system-prompts-vs-agents.md` | B / G | _pending promotion_ |

**Seeded** = ADR text exists at the seed location; promotion to
`knowledge/adr/` follows Phase 0 kickoff finalization.

## References

- `plans/steward_platform/governing_plan.md` §5-C — Primitive C scope
- `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` §Decision — commit policy
- `plans/steward_platform/3_primitive_C/shaping.md` §4.1 — KB structure spec
