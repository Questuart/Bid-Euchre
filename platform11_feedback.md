# Operator Feedback on Platform-11 Skill Learning Scope Lock

## Point-by-Point Feedback

### 1. Metrics
Borrow metrics from economy tracking: cost, token usage, lines added. Beef up tracking early but only implement skills on a few parameters to reduce degrees of freedom.

### Erratum: Claude Code Skills & /insights
- How does Claude Code skills and /insights work?
- Can we leverage the /insights function?
- Are there native skill learning tools in Claude Code we can borrow from?
- Are there public repos for similar agentic development (Open Claw, Hermes, etc) with skill learning loops we can draw from?

### 2. Focus Areas
Agree with approach — focus on merge time and review rounds for now. But start tracking ALL metrics we can so we create robust data for future skill loops.

### 3. Time of Day
Great idea — will need to track that.

### 4. MVP Approach
Makes sense for MVP.

### 5. See Erratum above

### 6. Issues Workflow
Agree with the issues workflow.

## Major Structural Feedback

### Outcome Model is Too Shallow
`success_rate * (1 / avg_minutes)` is fine as toy score but misleads unless you control for task difficulty. Fast completion != good routing if author-a mostly gets easy work and flex lanes get ugly edge cases.

**Add at minimum:**
- `complexity_estimate_at_dispatch`
- `session_type`
- `requires_review_gate` or severity class
- `rollback_or_rework_required`
- `acceptance_without_major_rewrite` flag

"Merged" is too coarse — a task can merge after painful cleanup and still look like success.

### Taxonomy is Make-or-Break
Manual taxonomy for MVP is right. But if mushy, whole thing becomes fake precision.

**Use these categories instead:**
- `convention_fix`
- `focused_bugfix`
- `test_repair`
- `doc_update`
- `investigation`
- `small_feature`
- `cross_module_refactor`
- `infra_or_tooling_change`
- `ambiguous_or_open_ended` (this one matters — routing failures come from ambiguity, not technical complexity)

### Exploration Policy
20% random exploration is too dumb operationally. Constrain it:
- Only explore below a risk threshold
- Never explore on high-blast-radius tasks
- Prefer exploration among plausible lanes, not fully random
- Decay exploration once confidence is high

### Skill Suggestion Pipeline Needs Stricter "Pattern" Definition
Task outcome records usually don't contain enough procedural detail to reconstruct reliable skills. They capture outcomes, not method.

**Candidate skill suggestions should use:**
- Task metadata
- Artifacts touched
- Structured operator notes or traces
- Review comments and correction patterns
- Source task provenance

**Minimum evidence threshold:**
- Repeated success on same task type
- Same major file or subsystem pattern
- Low review churn
- Consistent step sequence from traces or notes

### Baseline/Evaluation Too Thin
"2 overnight runs before and 2 after" is too flimsy. Define evaluation in matched cohorts:
- Same task types, session types, similar complexity buckets

**Measure:**
- Time to accepted completion
- Review rounds
- Rework rate
- Rollback rate
- Operator override rate
- Advisor recommendation acceptance rate (important — if operators constantly ignore advisor, problem may be trust not model quality)

### Storage
JSON is right for MVP. But structure as:
- Append-only outcomes event log
- Derived `lane_affinity.json`
- Optional snapshot/version metadata

Gives auditability and rebuild capability.

### Anti-Corruption Guardrails (Missing)
Add explicit guardrails:
- Dispatch advisor is advisory until validated
- No auto-promotion of skills
- No lane ranking shown as prestige scoreboard
- No routing based on fewer than N observations + minimum confidence
- Monitor for skew: one lane taking too much of one task type (no lane monocultures)

### Naming
Do NOT call Phase 1 a "learning algorithm." Call it:
- **Adaptive Dispatch Heuristics** or **Outcome-Informed Dispatch Advisor**
- Reserve "learning" for the broader platform capability
