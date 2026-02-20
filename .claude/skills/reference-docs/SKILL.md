---
name: reference-docs
description: Project reference documentation catalog. Use when you need authoritative details about game rules, architecture, data contracts, metrics, scoring, reproducibility, drift, quality bar, review checklist, agent workflow, or promotion workflow.
---

# Reference Documentation Catalog

Read these docs on-demand when working in the relevant area. Do NOT load all at once.

## Core Documentation (docs/01_core/)

| Doc | When to read |
|-----|-------------|
| `docs/01_core/ARCHITECTURE.md` | System design, module boundaries, import rules |
| `docs/01_core/EXPERIMENTS.md` | Experiment runner, configs, output structure |
| `docs/01_core/RULES.md` | Authoritative game rules (cards, tricks, bowers, scoring) |
| `docs/01_core/REPRODUCIBILITY.md` | Seeding, determinism, `--allow-nondeterministic` |
| `docs/01_core/DATA_CONTRACT.md` | Output schemas, JSONL fields, parquet contracts |
| `docs/01_core/METRICS.md` | Metric definitions, statistical requirements |
| `docs/01_core/SCORING.md` | Scoring rules, trick counting, set penalties |
| `docs/01_core/DRIFT.md` | Drift detection, golden seeds, version pinning |

## Agent & Workflow Documentation (docs/02_agent/)

| Doc | When to read |
|-----|-------------|
| `docs/02_agent/QUALITY_BAR.md` | Quality gates, review standards, merge criteria |
| `docs/02_agent/REVIEW_CHECKLIST.md` | PR review checklist items |
| `docs/02_agent/AGENTS.md` | Agent development workflow, worktree process |
| `docs/02_agent/AI_BOUNDARIES.md` | What agents may/may not do autonomously |
| `docs/02_agent/PROMOTION_WORKFLOW.md` | Model promotion pipeline and validation |

## PR Template

| Doc | When to read |
|-----|-------------|
| `.github/pull_request_template.md` | Creating or reviewing pull requests |
