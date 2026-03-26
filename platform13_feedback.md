# Operator Feedback on Platform-13 Second-Project Extraction Scope Lock

## Second Project Candidate Evaluation

### Smoke Test
Synthetic proof project. Create a minimal "hello-steward" project with a trivial test suite, a Makefile, and 2-3 source files. Proves the adapter interface works without real project overhead.

### Full Test
Project: Build a Commodities Balance Sheet based on Publicly Available RIN Data.
- User will define data sources and methodology
- Only need an MVP for proving — scrape, build balance sheet, etc. is enough

### Outside Validation
Ship to a friend to see if they can use it for their project by downloading from GH.

## Point-by-Point on Open Questions

1. Agent should review and assess the bid-euchre assumptions built into the platform boundary
2. Use judgement for the project adapter protocol — refine and tweak once established
3. Agree
4. Option B
5. Makes sense for reusable workflows

## Core Strength — Don't Lose This

"Platform-13 proves the boundary by running on a second project."

That's the right forcing function. Not docs, not architecture diagrams — execution in a foreign environment. If this works, you've built a reusable orchestration system. If it fails, you've exposed hidden coupling. Both are wins.

## Where This Will Break (Expect It)

### 1. Adapter Contract is Too Clean
In practice you'll hit:
- Hidden filesystem assumptions
- Implicit repo structure dependencies
- Hardcoded expectations about .claude/ layout, PR flow timing, branch naming, test output formats

The adapter will need to TRANSLATE mismatches:
```
def normalize_test_output(self, raw_output: str) -> TestResult: ...
def resolve_repo_paths(self) -> RepoLayout: ...
def pr_creation_strategy(self) -> PRStrategy: ...
```
Without this, Bid-Euchre assumptions sneak back into core/.

### 2. "Core is Generic" — Probably Not Yet
High-risk modules that likely leak project assumptions:
- task_queue.py → lane semantics and naming
- monitor.py → PR/CI expectations
- worker_pool.py → worktree + repo structure coupling

Better test than grep audit: Run the hello project and LOG EVERY ADAPTER CALL. If core ever branches on project behavior or assumes structure not provided by adapter → that's a leak.

### 3. Hello Project — Correct but Incomplete
Toy project proves: boot works, dispatch works, PR loop works.
Does NOT prove: monitoring robustness, failure handling, scheduling, concurrency edge cases.

**Two-step proof (non-negotiable):**
1. Hello project (fast fail)
2. One "slightly annoying" real project — 20-50 files, non-trivial tests, at least one failing edge case. That's where abstractions crack.

### 4. Packaging — Too Far Ahead
Premature to think about PyPI/git install/versioning. Only question now: Can core run outside the original repo without hacks?

**Recommendation:** Hardcode `pip install -e ../core`. Ignore distribution for Platform-13.

### 5. Biggest Hidden Risk: Claude Code Multi-Repo
More serious than treated. System assumes one repo context, one working directory, one .claude/runtime. Cross-repo introduces path ambiguity, state separation.

Need:
- Explicit repo root scoping in core
- Strict runtime isolation per project
- No reliance on cwd

### Missing: Clear Success Criteria

"task → PR → review → merge works" is not enough.

**Platform-13 is DONE when:**
- A second repo runs steward without modifying core/
- Adapter is ≤ ~150-250 LOC
- No Bid-Euchre strings appear in core runtime logs
- System survives: 1 failed test cycle, 1 rejected PR, 1 retry loop

If you don't include failure cases, you certify a brittle system.

## Recommended Tightened Plan

### Phase 1 — Brutal Extraction (2-3h)
Move everything "probably generic" into core. Don't overthink interface. Just make Bid-Euchre work via adapter.

### Phase 2 — Hello Project (2h)
Minimal adapter. Expect it to break. Patch interface until it runs clean.

### Phase 3 — Stress Test (3-4h)
Slightly real project. Force: failure, retry, PR rejection.

### Phase 4 — Only Then Formalize Interface
Lock ProjectAdapter. Document it.

## Bottom Line

Don't fall into: "We designed a clean abstraction, therefore it is clean."

This platform only becomes legitimate if the second project forces changes to core, and you accept and integrate those changes. If Platform-13 doesn't hurt a little, it didn't do its job.

**Analyst should review and push back where it disagrees.**
