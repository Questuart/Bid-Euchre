# Review Rubric: <artifact name>

**Artifact:** `path/to/artifact`
**Review type:** holistic | implementation | narrow-track | pre-promotion | post-merge
**Reviewer lane:** <analyst-a | analyst-b | analyst-c | analyst-d | flex-X | external>
**Date:** YYYY-MM-DD

## Review stance

One sentence naming the disposition. Example: "Skeptical; best-plausible-
plan standard; flag over-engineering; propose better alternatives. Fixed
constraints listed below should not be relitigated."

## Rubric dimensions

Each review should return an explicit grade (A / A- / B+ / B / B- / C+ /
C / below) per dimension with one-sentence reasoning. Dimensions are
artifact-type-specific — the list below is the default for a governing
plan; adapt for ADRs, sub-plans, or code reviews.

1. **Strategic clarity** — does the artifact define the right destination?
2. **Scope discipline** — proportional to the problem, or inflated?
3. **Simplicity and leverage** — where is bespoke scope high vs. value?
4. **Execution realism** — shippable under stated constraints?
5. **Directive quality** — are prescribed methods the right shape?
6. **Risk handling** — do risks cover real failure modes?
7. **Adaptability** — can the plan pivot without rewriting?
8. **Cross-reference integrity** — do load-bearing references resolve?

## Finding schema

Every finding must have a stable ID scheme that does not collide with
prior reviews. Default: `H<n>` for holistic findings, `I<n>` for
implementation findings. For same-artifact review chains, declare the ID
offset (e.g., "avoid F1-F13 and G1-G13 — start at H1 / I1").

Per finding:
- **ID** — e.g., `I4`
- **Severity** — High | Medium | Low
- **Location** — file path + line(s) or section ID
- **Observation** — what's wrong in one paragraph
- **Recommended fix** — concrete edit or alternative, not "consider X"
- **Rationale** — why this matters if not fixed

Example worked finding: "I4 (Medium): §15.4 says 'four prompts' but §15.2
lists five. Fix: update §15.4 to 'five prompts + disposition' and pick an
axis-vs-modifier model for Re-evaluation. Rationale: downstream digest
parser will ship with the wrong arity if shipped as-is."

## Deliverables

- Per-dimension grade + reasoning
- Overall grade
- Finding list (stable IDs, severity, location, fix, rationale)
- Final recommendation — PROMOTE-AS-IS | PROMOTE-AFTER-FIXES | REVISE
- Optional: omissions the rubric didn't ask about but the reviewer flags

## Output path convention

Reviews land at `plans/<initiative>/<artifact>_review_<lane>.md`. For
pre-promotion reviews the convention is `..._final_review_<lane>.md`.
Reviewers should ensure the output filename matches the handoff's stated
destination — filename drift breaks downstream automation.
