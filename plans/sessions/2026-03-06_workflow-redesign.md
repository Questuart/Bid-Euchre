# Workflow Redesign: Automated Review Pipeline

## Goal

Replace the current manual merge workflow with a two-stage automated pipeline
plus GitHub-native Codex pre-merge review:

1. **Pre-Merge Gate** — `/reviewing-changes` publishes a GitHub commit status; branch protection enforces it alongside CI.
2. **Codex Pre-Merge Review** — GitHub-native Codex auto-reviews every PR before merge. Advisory during rollout; merge happens manually after Codex review is visible.

All review findings are recorded as follow-up issues (not commits on the original branch). Corrective PRs are opened only after the original PR merges, creating a durable audit trail of `plan PR -> Codex review comments -> code PR -> reviewing-changes status -> follow-up issues -> corrective PRs`.

### Operating Model

> **Claude is the default authoring agent, Codex is the GitHub-native pre-merge reviewer, and GitHub is the system of record for merge gates and review artifacts.**

| Role | Agent | Scope |
|------|-------|-------|
| Plan authoring | Claude | Writes plan files, opens plan PRs |
| Plan review | Codex (GitHub-native) | Auto-reviews plan PRs via GitHub integration |
| Code authoring | Claude | Implements from approved plan, opens code PRs |
| Pre-merge review | Claude (local) | Runs `/reviewing-changes`, publishes GitHub commit status |
| Pre-merge advisory | Codex (GitHub-native) | Auto-reviews code PRs via GitHub integration |
| Final approval | Human | Reviews Codex comments; merges manually during rollout |

### Acceptance Criteria

- [x] Code PRs require both `CI` and `reviewing-changes` GitHub checks to merge
- [x] `/reviewing-changes` publishes a GitHub commit status (not just chat output)
- [x] ALL review findings become follow-up issues (no auto-fix commits on original branch)
- [x] Follow-up issues carry category labels (`fix:bug`, `fix:convention`, `fix:test`, `fix:docs`, `fix:process`)
- [x] Corrective PRs are opened only after the original PR merges, referencing the follow-up issue
- [x] Plan/docs-only PRs get a lightweight governance check (not skipped by CI)
- [x] Stuck `reviewing-changes` status (pending >1 hour) has a recovery path
- [ ] Codex pre-merge review is documented and operationalized (GitHub-native, no API key)
- [ ] Audit analysis script can query follow-up patterns from GitHub-native artifacts
- [ ] Merge happens only after Codex review is visible during rollout

---

## Completed PRs (1-5)

| PR | Title | Merged As | Files |
|----|-------|-----------|-------|
| 1 | Governance check workflow | #559 | `.github/workflows/governance.yml` |
| 2 | Review commit status infrastructure | #561 | `scripts/internal/set_review_status.sh`, `.claude/rules/60_review_gate.md` |
| 3 | Modified `/reviewing-changes` skill | #562 | `.claude/skills/reviewing-changes/SKILL.md`, `HANDOFF_TEMPLATE.md` |
| 4 | Shared hook + fallback workflow | #563 | `.claude/settings.json`, `.claude/hooks/post-pr-review.sh`, `.github/workflows/review_status_fallback.yml` |
| 5 | Branch protection configuration | Admin setup | Required checks: `tests`, `governance`, `reviewing-changes` |

### Amendment to PR 3 (included in PR 6)

- Removed `gh pr merge --auto --squash` from the success path
- Verdict changed from "READY TO MERGE" to "READY FOR CODEX/HUMAN REVIEW"
- Handoff template updated to show Codex review status instead of auto-merge status

### Amendment to PR 5 (operational)

- Required checks remain `tests`, `governance`, `reviewing-changes`
- No Codex-specific required check added (GitHub-native Codex does not expose a stable status context)
- Manual merge after Codex review during rollout (no auto-merge until Codex is proven on 3-5 PRs)

---

## Remaining PRs (6-8)

### PR 6: Rewrite workflow docs for GitHub-native Codex pre-merge review

**Files:**
- Edit `plans/sessions/2026-03-06_workflow-redesign.md` (this file)
- Edit `.claude/skills/reviewing-changes/SKILL.md`
- Edit `.claude/skills/reviewing-changes/HANDOFF_TEMPLATE.md`
- Edit `.claude/rules/60_review_gate.md`

**Changes:**
- Define Codex as GitHub-native pre-merge reviewer (not API workflow)
- State explicitly: `reviewing-changes` is the only formal automated gate we control
- State explicitly: merge happens only after Codex review is visible during rollout
- Remove all API-key, custom OpenAI workflow, and post-merge audit language
- Remove `gh pr merge --auto --squash` from `/reviewing-changes` success path
- Update audit trail to: `plan PR -> Codex review comments -> code PR -> reviewing-changes status -> follow-up issues -> corrective PRs`

**Acceptance:**
- No `OPENAI_API_KEY` in the plan
- No custom Codex workflow/script files in the planned scope
- The plan no longer claims fully automatic post-merge Codex review

---

### PR 7: Operationalize Codex pre-merge review in PR workflow

**Files:**
- Edit `.github/pull_request_template.md`
- Create `docs/02_agent/CODEX_GITHUB_REVIEW.md`
- Edit `CLAUDE.md` if needed for author workflow

**Changes:**
- Add a PR template section `## Codex Review` with checkboxes:
  - `Codex auto-review expected/enabled`
  - `Any Codex blocking comments addressed`
  - `Residual Codex follow-ups captured as issues`
- Document owner setup steps:
  - Connect ChatGPT/Codex to GitHub
  - Enable Codex automatic PR review for this repo
- Document Claude behavior:
  - After `reviewing-changes=success`, wait for/read Codex review on the PR
  - Fix anything that must be fixed before merge
  - Convert non-blocking Codex findings into follow-up issues if needed

**Acceptance:**
- The repo has a documented, repeatable no-API-key Codex review workflow
- A new PR clearly shows whether Codex review has happened and what remains

---

### PR 8: Re-scope audit analysis to GitHub-native artifacts

**Files:**
- Create `scripts/internal/audit_analysis.py`
- Optionally add usage docs in `docs/02_agent/AGENTS.md`

**Scope:** Data we actually have without API calls:
- Merged PRs
- `reviewing-changes` status results
- Follow-up issues and corrective PRs
- Labels such as `follow-up`, `fix:*`
- Optionally Codex comments/reviews (only if GitHub metadata shape is verified from a live PR)

**Acceptance:**
- The script can report:
  - Merged PR count
  - Follow-up issue rate
  - Corrective PR rate
  - Categories of follow-up work
  - Per-PR audit trail from original PR to follow-up issues/PRs
- Do not promise Codex-comment analytics until the GitHub metadata is confirmed from a live run

---

## Dependency Chain

```
PRs 1-5: COMPLETE (governance, status infra, skill, hook, branch protection)

PR 6 (docs rewrite) — in progress
PR 7 (operationalize Codex) — depends on PR 6
PR 8 (audit analysis) — independent of PR 7, needs follow-up data to exist
```

---

## Configuration Summary

### GitHub Secrets Required

None. GitHub-native Codex requires no API key.

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

### GitHub Labels

| Label | Color | Description |
|-------|-------|-------------|
| `follow-up` | `#fbca04` | Applied to follow-up issues and corrective PRs from review |
| `fix:bug` | `#d73a4a` | Follow-up fixing a bug |
| `fix:convention` | `#0075ca` | Follow-up fixing a convention violation |
| `fix:test` | `#e4e669` | Follow-up adding missing tests |
| `fix:docs` | `#0e8a16` | Follow-up fixing documentation |
| `fix:process` | `#c5def5` | Follow-up fixing a process issue |

### Branch Protection Rules

| Setting | Value |
|---------|-------|
| Required status checks | `tests`, `governance`, `reviewing-changes` |
| Require branches to be up to date | Yes |
| Enforce admins | Rollout: Yes. Steady-state: No (after ~10 PRs) |
| Required reviews | Rollout: 1 human approval. Steady-state: re-evaluate after Codex is proven |

### Review Severity Config (`.claude/rules/60_review_gate.md`)

| Severity | Merge effect | Action |
|----------|-------------|--------|
| BLOCK | Blocked | Must fix on current PR |
| WARN | Allowed | Follow-up issue created; corrective PR opened post-merge |
| INFO | Allowed | Noted in report only |

---

## Owner Setup Checklist

These require manual admin/GitHub configuration — Claude should not automate them.

### 1. Create Labels

```bash
gh label create "follow-up"         --color "fbca04" --description "Follow-up issue or corrective PR from review"
gh label create "fix:bug"           --color "d73a4a" --description "Follow-up fixing a bug"
gh label create "fix:convention"    --color "0075ca" --description "Follow-up fixing a convention violation"
gh label create "fix:test"          --color "e4e669" --description "Follow-up adding missing tests"
gh label create "fix:docs"          --color "0e8a16" --description "Follow-up fixing documentation"
gh label create "fix:process"       --color "c5def5" --description "Follow-up fixing a process issue"
```

### 2. Connect Codex to GitHub

- Connect ChatGPT/Codex to your GitHub account
- Enable Codex automatic PR review for this repo (or for your PRs)
- Confirm one test PR actually receives Codex review automatically

### 3. Verify Actions Permissions

Settings > Actions > General:
- **Actions permissions:** Allow all actions (or at minimum `actions/checkout`)
- **Workflow permissions:** Read and write permissions

### 4. Rollout: Require Human Approval

Until Codex auto-review is proven reliable on 3-5 real PRs:

```bash
gh api repos/Questuart/Bid-Euchre/branches/main/protection -X PUT --input - <<< '{"required_status_checks":{"strict":true,"contexts":["tests","governance","reviewing-changes"]},"enforce_admins":true,"required_pull_request_reviews":{"required_approving_review_count":1},"restrictions":null}'
```

After Codex is proven, drop the human approval requirement:

```bash
gh api repos/Questuart/Bid-Euchre/branches/main/protection -X PUT --input - <<< '{"required_status_checks":{"strict":true,"contexts":["tests","governance","reviewing-changes"]},"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null}'
```

### 5. Remove Duplicate Local Hook (Cleanup)

After PR 4 merged, remove the PostToolUse/Bash hook from `.claude/settings.local.json`
if still present (it's now in the shared `.claude/settings.json`).

---

## Removed Scope

The following were in the original plan but have been removed in favor of
GitHub-native Codex integration:

- `OPENAI_API_KEY` as a required secret
- `.github/workflows/plan_review.yml` (custom Codex API workflow)
- `scripts/internal/codex_plan_review.py`
- `.github/workflows/post_merge_review.yml` (custom post-merge audit)
- `scripts/internal/codex_post_merge_review.py`
- `.github/ISSUE_TEMPLATE/post_merge_review.md`
- `codex-plan-review` commit status context
- Post-merge Codex audit automation
- `post-merge-review` label

---

## Outcome

(To be filled after implementation)
