# PR Prompt Templates (Robust, Parallel-Safe)

These templates are designed for **cheap agents** operating in a repo with strict determinism + reproducibility requirements, and for **parallel** PR execution without scope leaks.

## 🚨 DEFAULT: Full Permissions Mode (CRITICAL)

**Run ALL PR agents in full permissions mode by default** (Cursor: `required_permissions: ["all"]`).

**WHY THIS IS CRITICAL**: macOS TLS/keychain sandbox issues (e.g., `OSStatus -26276`, certificate verification failures) prevent reliable GitHub API access via `gh` in restricted sandbox modes. Full permissions mode ensures TLS certificate validation works reliably for all `gh` commands.

## When to use which template

- Use the **SHORT** template for:
  - 1–3 files
  - docs-only changes
  - small bugfixes with obvious chokepoints

- Use the **LONG** template for:
  - multi-file changes
  - changes that require coordinating tests/fixtures/contracts
  - anything where scope creep is likely
  - anything that touches core sim/scoring/results contracts

## Multi-agent / parallel PR guardrails (important)

If you are running multiple agents in parallel:
- Treat scope as a hard lock. Do not "helpfully" touch shared files outside scope.
- Avoid shared/central files unless explicitly scoped (e.g., top-level README, docs/README.md, AGENTS.md, pyproject.toml).
- Always prove you started from `main`.
- Always produce scope proof even if `git fetch` is blocked.
- If you discover required changes outside scope that touch shared files: **STOP and report**.

## Parallel Mode: git worktrees (REQUIRED for multi-agent runs)

**Rationale (why this is required):**
- Multiple agents switching branches in the same working directory causes accidental commits to `main` or to the wrong branch.
- Worktrees isolate each agent in its own directory, eliminating branch-switch races.

**Hard rule (parallel runs):** do NOT branch-switch the shared checkout. Create **one worktree per agent/PR** and do all edits/commits from inside that worktree.

## Default: Worktree Mode (Parallel-Safe)

**WHY THIS IS THE DEFAULT:** Prevents multiple agents from fighting over `main` branch state in the same working directory. Even single-agent runs should use worktrees to avoid accidental commits to `main`.

**Hard rule:** If running >1 agent in parallel, you MUST use worktrees. Single-agent runs SHOULD also use worktrees for safety.

**Note:** `gh` still requires HTTPS/TLS even if `git` uses SSH for transport.

## Worktree Mode (DEFAULT) — Copy/Paste Block

```bash
# Set unique worktree identifiers
WT_NAME="pr<NN>-<slug>"  # e.g., pr42-fix-bug
WT_DIR="../wt-$WT_NAME"  # relative to repo root

# From repo root: create worktree and switch to it
git fetch origin
git worktree add "$WT_DIR" origin/main
cd "$WT_DIR"

# Create feature branch inside worktree
git checkout -b "$WT_NAME"

# From this point: ALL commands run inside the worktree directory
# Edit files, run tests, commit, push, create PR...
```

## Single working tree (single-agent only / not parallel-safe)

**WARNING:** This mode is NOT safe for parallel runs. Only use for single-agent execution.

```bash
# Classic mode - NOT for parallel execution
git checkout main
git checkout -b <branch-name>
# Edit, commit, etc...
```

## Local execution note (Cursor)

These prompts assume the agent runs in **Cursor's local terminal** (commands execute on the local machine).
To make PR creation reliable:
- `GH_TOKEN` must be set in the environment (non-interactive auth).
- `gh api user -q .login` must succeed (non-interactive).
- `git ls-remote origin HEAD` must succeed (non-interactive).
- `git remote -v` must show SSH for origin (`git@github.com:...`).

**SSH vs HTTPS clarification**:
- `git` uses the origin remote protocol (SSH or HTTPS).
- `gh` uses HTTPS API regardless.
- SSH fixes `git` transport, but `gh` still requires TLS certificate validation.
- Therefore: SSH does NOT replace TLS requirements for `gh` commands.

---

# REPO PR AGENT PROMPT TEMPLATE (ROBUST SHORT TEMPLATE FOR CHEAPER AGENTS — PARALLEL-SAFE)

ROLE
You are a patch-focused maintainer. Implement ONLY what this PR asks. No refactors, no drive-by cleanups.

STYLE
- Minimal diff, surgical edits.
- Determinism-first: do not introduce nondeterminism.
- Prefer precise fixes over cleanup.

ABSOLUTE RULES
- Do NOT claim a PR exists until you have a PR URL (from gh).
- Do NOT stop after “Step 0” unless a STOP CONDITION applies.
- FINAL RESPONSE must include validation proof + PR body header validation + clean workspace proof.
- Paste terminal outputs **verbatim** when asked (do not summarize).

PARALLEL-SAFE RULES
- Do not touch shared/central files unless explicitly scoped.
- If you discover required changes outside scope that touch shared files: STOP and report.
- Do not “fix” nearby lint/docs unless it is strictly required for the scoped change.

GIT HYGIENE (required)
- Never work or commit on main.
- Branch before edits.
- In parallel runs: do NOT branch-switch the shared checkout; use git worktrees (one worktree per agent/PR).
- Stage explicitly (no `git add .`).
- Single commit per PR.
- Return workspace to clean main at the end.

PERMISSIONS / GH ACCESS (critical)
- Run GitHub + git-remote checks early (Step 0.2).
- If `gh` fails due to auth/TLS/permissions/locks:
  - Do ONE retry in full-permissions mode (Cursor: required_permissions: ["all"]).
  - If still failing: STOP and report (manual PR mode is not allowed unless explicitly requested by the user).

PR Title
<one line>

Goal
<end state>

Non-goals
- <bullet>
- <bullet>

Hard Scope (Allowed files only)
- <file1>
- <file2>
- <new_file3>

If any other file is needed: smallest necessary change + list under “Scope exceptions” in final response.

Hard Gates / Acceptance
- make check passes (or state exactly what is missing locally; rely on CI)
- determinism preserved
- no generated artifacts committed
- baseline/invariant tests pass unless explicitly listed
- PR body MUST include EVERY “##” section header from .github/pull_request_template.md
- Final response MUST include proof snippets (see below)

DOC COMMAND VALIDATION (required for docs changes that add/modify commands)
For every command you add or change, include proof for at least one of:
- `PYTHONPATH=src python <script> --help` (paste relevant flag lines), OR
- `ls <referenced path>` (for referenced configs/suites/scripts)

STOP CONDITIONS (only)
- Required files/configs/tests can’t be found after searching (rg/grep).
- You cannot run any validations at all (missing python tooling) AND cannot rely on CI.
- GitHub auth cannot be made to work after one full-permissions retry (Step 0.2).

If STOP: say exactly what you searched and what’s missing/failing.

────────────────────────────────────────
Step -1 — Git setup (MUST; no code)

Run + paste outputs verbatim:
- git status
- git branch --show-current
- git fetch origin (or “fetch blocked”)

Then:
- Single-agent / non-parallel mode:
  - You MUST be on main before branching:
    - cd out of worktree (cd - or cd ..)
    - git status -sb
  - Create branch:
    - git checkout -b <branch-name>

- Parallel Mode (worktrees; REQUIRED for multi-agent runs):
  - Do NOT branch-switch the shared checkout.
  - Worktree creation (from the main repo root):
    - BRANCH="<branch-name>"
    - WT_DIR="../.worktrees/$BRANCH"
    - mkdir -p ../.worktrees
    - git fetch origin (or “fetch blocked”)
    - git worktree add -b "$BRANCH" "$WT_DIR" origin/main
    - cd "$WT_DIR"
  - Proof (required in template):
    - git worktree list
    - git status -sb
    - git merge-base --is-ancestor main HEAD && echo "based on main ✅" || echo "NOT based on main ❌"
  - Work in the worktree as normal (edit, test, commit, push, gh pr create).
  - After PR creation, cleanup (from the original repo root):
    - cd -   (or cd back to the main repo root)
    - git worktree remove "$WT_DIR"
    - (optional) rmdir ../.worktrees  (only if empty)

BASE PROOF (required)
- git merge-base --is-ancestor main HEAD && echo "based on main ✅" || echo "NOT based on main ❌"
If NOT based on main ❌: STOP and restart from main.

────────────────────────────────────────
Step 0 — Confirm anchors (MUST; no code)

Run + paste minimal proof (rg/grep output snippets) that you found:
- the chokepoint(s) you will edit
- the config/test anchors you will use

Then state: “I will edit only <scoped file list>.”
IMPORTANT: Continue to implementation unless STOP CONDITIONS apply.

────────────────────────────────────────
Step 0.2 — GitHub + remote capability check (MUST early)

Run + paste outputs verbatim:
- echo "GH_TOKEN=${GH_TOKEN:+set}"
- gh --version (or “gh missing”)
- gh auth status (or failure)
- gh api user -q .login (or failure)
- gh api https://api.github.com/meta >/dev/null && echo "GitHub API TLS OK ✅" || echo "GitHub API TLS FAIL ❌"
- gh repo view Questuart/Bid-Euchre --json nameWithOwner,defaultBranchRef,url
- git remote -v (must show SSH: git@github.com:)
- git ls-remote origin HEAD (or failure)

HARD RULE:
- If "GitHub API TLS FAIL ❌" → STOP and re-run the entire agent in full permissions mode (Cursor: required_permissions: ["all"]).
- If still FAIL in full permissions → STOP and paste the error from: `gh api https://api.github.com/meta`

If git remote shows HTTPS instead of SSH:
- git remote set-url origin git@github.com:Questuart/Bid-Euchre.git
- Re-run git remote -v to confirm

SSH vs HTTPS note:
- `git` uses the origin remote protocol (SSH or HTTPS)
- `gh` uses HTTPS API regardless
- Therefore SSH does NOT replace TLS requirements for `gh`

If auth is broken:
- Do ONE retry in full permissions (Cursor: required_permissions: ["all"]).
- Re-run the same checks once.
- If still failing: STOP and report.

────────────────────────────────────────
Implementation (do the work)

1) Make minimal changes to achieve Goal.
2) Add minimal tests needed for Goal.
3) Keep outputs deterministic (sort keys / avoid nondeterministic iteration).

────────────────────────────────────────
Validation (MUST try)

Run:
- make check

If deps missing:
- run what you can (e.g., make repo-lint / make lint / pytest -q) and state exactly what failed.

HARD RULE:
- If any existing test fails due to your change: STOP, do not commit, report failure.

PROOF REQUIRED:
- Paste the last ~10 lines of output from make check (or fallback command).

────────────────────────────────────────
Diff hygiene (MUST)

Run + paste outputs verbatim:

Preferred (if fetch worked):
- git diff --name-only origin/main...HEAD

Fallback (if fetch blocked OR origin/main unavailable):
- git diff --name-only main...HEAD

And always:
- git show --name-status --oneline -1

Must match Hard Scope.

────────────────────────────────────────
Commit + push (MUST)

- git add <file1> <file2> <new_file3>
- git diff --cached --name-only (paste; must match scope)
- git commit -m "<PR Title>"
- git push -u origin HEAD

Single-commit proof (required):
- git log --oneline --decorate -3
- git show --stat -1

────────────────────────────────────────
PR body (MUST fill template completely)

- (printf "Summary\n- <b1>\n- <b2>\n- <b3>\n\n"; cat .github/pull_request_template.md) > pr_body_raw.md
- Fill ALL sections in pr_body_raw.md and save as pr_body.md

HARD GATE (header match):
- rg -n "^## " .github/pull_request_template.md (or grep)
- rg -n "^## " pr_body.md
These header lists MUST match (same headers, no omissions).

PROOF REQUIRED:
“PR body validation passed ✅ (all template headers present)”

────────────────────────────────────────
Create PR (gh preferred)

Branch context gate (required):
- test "$(git branch --show-current)" != "main" && echo "On feature branch ✅" || (echo "On main ❌" && exit 1)

Try:
- BRANCH="$(git branch --show-current)"
- gh pr create --base main --head "$BRANCH" --title "<PR Title>" --body-file pr_body.md

If it fails:
- Do ONE remediation attempt (auth login OR full permissions: required_permissions: ["all"])
- Retry once
- If still fails: STOP and report (manual PR mode is not allowed unless explicitly requested by the user).

If PR is created successfully:
- gh pr diff --name-only (must match scope)
- gh pr checks --watch (or state “checks unavailable/pending”)

PR ID PROOF (required if PR created):
- gh pr view --json number,url,headRefName --jq '{number:.number,url:.url,branch:.headRefName}'

Cleanup always:
- rm -f pr_body.md pr_body_raw.md

────────────────────────────────────────
Worktree cleanup (MUST)

**WARNING:** Do NOT run `git checkout main` repeatedly in parallel runs - this causes branch conflicts between agents.

- Single-agent / non-parallel mode:
  - cd out of worktree (cd - or cd ..)
  - git worktree remove "$WT_DIR"
  - git worktree prune

PROOF REQUIRED:
- Paste the final git status -sb output showing clean workspace.

────────────────────────────────────────
FINAL RESPONSE (MUST)

Return exactly:
1) Branch name + commit SHA
2) PR URL + number (OR “PR not created” + error summary)
3) Files changed/added
4) Minimal diff summary
5) Tests added/updated
6) Commands run + local/CI gate status (include validation proof snippet)
7) Scope exceptions (if any)
8) Confirmation workspace returned to clean main (include git status proof)
9) gh auth status result (OK / retried with ["all"] / failed)
10) “PR body validation passed ✅ (all template headers present)”

---

# REPO PR AGENT PROMPT TEMPLATE (ROBUST LONG FORM — PARALLEL-SAFE)

ROLE
You are a patch-focused maintainer working in a Python repo. Implement exactly what this PR asks—no refactors, no drive-by cleanups.

STYLE
- Minimal diff, surgical edits.
- Prefer small pure helpers over restructuring.
- Determinism-first: do not introduce nondeterminism.
- If requirements conflict, proceed with the smallest necessary change and document it under “Scope exceptions”.

ABSOLUTE RULES (do not violate)
- Do NOT claim a PR exists until you have a PR URL (from gh).
- Do NOT stop after “Step 0 / Step 0.5” unless a STOP CONDITION applies.
- FINAL RESPONSE must include validation proof + PR body header validation + clean workspace proof.
- Paste terminal outputs **verbatim** when asked (do not summarize).

PARALLEL-SAFE RULES
- Hard scope is a lock. Do not touch shared files outside scope.
- Do not edit central/index files unless explicitly scoped (README, docs/README.md, AGENTS.md, pyproject.toml, Makefile).
- If required change touches shared files outside scope: STOP and report.

GIT HYGIENE (required)
- Do not work or commit on main.
- Create/switch to a branch before editing.
- In parallel runs: do NOT branch-switch the shared checkout; use git worktrees (one worktree per agent/PR).
- Stage explicitly (no git add .) and only within scope.
- Single commit per PR unless explicitly instructed otherwise.
- Push branch and create a PR (gh preferred).
- PR body MUST use .github/pull_request_template.md (prepend summary bullets).
- Default to creating the PR automatically via gh.
- Return workspace to clean main at the end.

PERMISSIONS / ENV / GH ACCESS (critical)
- You MUST run an early GitHub + git-remote capability check (Step 0.2).
- If git/gh fails due to TLS certificates, keychain/auth, or permission/lock errors (e.g., x509, CAfile, index.lock, refs/*.lock):
  - Do ONE retry in “full permissions” mode (Cursor: required_permissions: ["all"]).
  - If it still fails: STOP and report (manual PR mode is not allowed unless explicitly requested by the user).

CONTRACT

PR Title
<ONE LINE TITLE>

Goal
<What must be true after this PR?>

Non-goals
- <bullet>
- <bullet>

Hard Scope (Allowed files)
Touch only:
- <path/to/file1>
- <path/to/file2>
- <path/to/new_file3>

If any other file seems required:
Proceed with the smallest necessary change and document it under “Scope exceptions” in the final response.

Hard Gates / Acceptance Criteria
- make check passes (or CI equivalent if deps missing locally; be explicit).
- Existing integration/baseline/invariants tests pass unless explicitly listed below.
- Output/data contracts remain stable (no renames/removals; additive only unless stated).
- No generated artifacts committed (data/runs, reports, etc).
- Deterministic behavior preserved.
- PR body MUST include EVERY “##” section header from .github/pull_request_template.md (no omissions).
- Final response MUST include proof snippets (validation + clean workspace) and header validation confirmation.

Inputs / Ground Truth
- Repo is authoritative: prefer what exists in code/docs over assumptions.
- Rules/Specs (authoritative):
  - <rule 1>
  - <rule 2>

Expected Outputs (New/Changed)
- New keys / files / behaviors:
  - <explicit list>
- Backward compatibility expectations:
  - <explicit list>

STOP CONDITIONS (only valid reasons to stop early)
- The repo or required file(s) do not exist in the workspace.
- The specified config/test anchor cannot be found AND you cannot identify an equivalent after searching (rg/grep).
- You cannot run any validations at all (missing python tooling) AND cannot rely on CI.
- GitHub auth cannot be made to work after one full-permissions retry (Step 0.2).

If STOP: explain exactly what you searched and what is missing/failing.

──────────────────────────────────────────────────────────────────────────────
STEP -1 — GIT SETUP (NO CODE)

Run and PASTE outputs verbatim:
- git status
- git branch --show-current
- git fetch origin (if blocked, say “fetch blocked” and continue)

Then:
- Single-agent / non-parallel mode:
  - You MUST be on main before branching:
    - cd out of worktree (cd - or cd ..)
    - git status -sb
  - Create/switch to branch:
    - git checkout -b <branch-name>

- Parallel Mode (worktrees; REQUIRED for multi-agent runs):
  - Do NOT branch-switch the shared checkout.
  - Worktree creation (from the main repo root):
    - BRANCH="<branch-name>"
    - WT_DIR="../.worktrees/$BRANCH"
    - mkdir -p ../.worktrees
    - git fetch origin (or “fetch blocked”)
    - git worktree add -b "$BRANCH" "$WT_DIR" origin/main
    - cd "$WT_DIR"
  - Proof (required in template):
    - git worktree list
    - git status -sb
    - git merge-base --is-ancestor main HEAD && echo "based on main ✅" || echo "NOT based on main ❌"
  - Work in the worktree as normal (edit, test, commit, push, gh pr create).
  - After PR creation, cleanup (from the original repo root):
    - cd -   (or cd back to the main repo root)
    - git worktree remove "$WT_DIR"
    - (optional) rmdir ../.worktrees  (only if empty)

BASE PROOF (required)
- git merge-base --is-ancestor main HEAD && echo "based on main ✅" || echo "NOT based on main ❌"
If NOT based on main ❌: STOP and restart from main.

──────────────────────────────────────────────────────────────────────────────
STEP 0 — CONFIRM ANCHORS (NO CODE)

Provide 3–5 lines of proof that you located the chokepoints (rg/grep output snippets or file/function names if rg unavailable):
- emitter/chokepoint location(s)
- config/contract keys location(s)
- relevant tests/fixtures location(s)

Then state exactly:
“I will edit only <scoped file list>.”

IMPORTANT: After Step 0 you MUST continue unless a STOP CONDITION applies.

──────────────────────────────────────────────────────────────────────────────
STEP 0.2 — GITHUB + REMOTE CAPABILITY CHECK (HARD GATE; NO CODE)

Run and paste outputs verbatim:
- echo "GH_TOKEN=${GH_TOKEN:+set}"
- gh --version (or “gh missing”)
- gh auth status (or failure)
- gh api user -q .login (or failure)
- gh api https://api.github.com/meta >/dev/null && echo "GitHub API TLS OK ✅" || echo "GitHub API TLS FAIL ❌"
- gh repo view Questuart/Bid-Euchre --json nameWithOwner,defaultBranchRef,url
- git remote -v (must show SSH: git@github.com:)
- git ls-remote origin HEAD (or failure)

HARD RULE:
- If "GitHub API TLS FAIL ❌" → STOP and re-run the entire agent in full permissions mode (Cursor: required_permissions: ["all"]).
- If still FAIL in full permissions → STOP and paste the error from: `gh api https://api.github.com/meta`

If git remote shows HTTPS instead of SSH:
- git remote set-url origin git@github.com:Questuart/Bid-Euchre.git
- Re-run git remote -v to confirm

SSH vs HTTPS note:
- `git` uses the origin remote protocol (SSH or HTTPS)
- `gh` uses HTTPS API regardless
- Therefore SSH does NOT replace TLS requirements for `gh`

If any of the above fails:
- Do ONE retry in full permissions mode (Cursor: required_permissions: ["all"]).
- Re-run the same checks once.
- If still failing: STOP and report.

──────────────────────────────────────────────────────────────────────────────
STEP 0.5 — FIND AND LIST CONTRACT TESTS (NO CODE)

List any tests/fixtures likely to break:
- file path
- test name
- what it asserts

Then state exactly how you will update them (minimal).

If any existing test is expected to fail due to the fix:
- State which test and why.
- Proceed only if the failure is due to the test asserting OLD (buggy) behavior.
- Otherwise STOP and report (do not commit).

──────────────────────────────────────────────────────────────────────────────
IMPLEMENTATION PLAN (Do this in-order)

1) <subtask 1>
2) <subtask 2>
...

──────────────────────────────────────────────────────────────────────────────
IMPLEMENTATION

- Make the smallest edits necessary.
- Do not introduce new entrypoints/runners unless explicitly required.
- Keep comparisons/order deterministic (sort where needed).
- Avoid brittle tests (no exact-value asserts unless required).

DOC COMMAND VALIDATION (required for docs that add/modify commands)
For every command you add or change, include proof for at least one of:
- `PYTHONPATH=src python <script> --help` (paste relevant flag lines), OR
- `ls <referenced path>` (for referenced configs/suites/scripts)

──────────────────────────────────────────────────────────────────────────────
TESTS / VALIDATION (MUST TRY)

Run:
- make check

If local deps missing:
- run what you can (e.g., make repo-lint / make lint / pytest -q) and state exactly what failed.

HARD RULE:
- If any existing test fails due to your change: STOP, do not commit, report which test failed and why.

PROOF REQUIRED:
- Paste the last ~10 lines of make check (or fallback) output into your final response.

──────────────────────────────────────────────────────────────────────────────
BRANCH / DIFF HYGIENE

Run and paste outputs (must match scope):
Preferred (if fetch worked):
- git diff --name-only origin/main...HEAD

Fallback (if fetch blocked OR origin/main unavailable):
- git diff --name-only main...HEAD

And always:
- git show --name-status --oneline -1

──────────────────────────────────────────────────────────────────────────────
PUBLISH (Required)

1) Stage only scoped files:
- git add <file1> <file2> <new_file3>
- git diff --cached --name-only (paste; must match scope)

2) Single commit:
- git commit -m "<PR Title>"

3) Push:
- git push -u origin HEAD

Single-commit proof (required):
- git log --oneline --decorate -3
- git show --stat -1

──────────────────────────────────────────────────────────────────────────────
CREATE PR BODY (Required; MUST use repo PR template and fill ALL sections)

1) Create raw body (summary + template):
- (printf "Summary\n- <bullet 1>\n- <bullet 2>\n- <bullet 3 (optional)>\n\n"; cat .github/pull_request_template.md) > pr_body_raw.md

2) Fill ALL placeholders and sections; save as pr_body.md.

HARD GATE (header match):
- rg -n "^## " .github/pull_request_template.md (or grep)
- rg -n "^## " pr_body.md
These header lists MUST match (no missing sections).

PROOF REQUIRED (final response):
- “PR body validation passed ✅ (all template headers present)”

──────────────────────────────────────────────────────────────────────────────
CREATE PR (gh preferred)

Branch context gate (required):
- test "$(git branch --show-current)" != "main" && echo "On feature branch ✅" || (echo "On main ❌" && exit 1)

1) Attempt PR creation via gh:
- BRANCH="$(git branch --show-current)"
- gh pr create --base main --head "$BRANCH" --title "<PR Title>" --body-file pr_body.md

2) If gh fails:
- Do ONE remediation attempt:
  - If auth missing: fix auth / token / permissions (Cursor: required_permissions: ["all"])
- Retry gh pr create once.

3) If still failing:
- STOP and report (manual PR mode is not allowed unless explicitly requested by the user).
- Do NOT claim PR exists.

4) If PR created successfully:
- gh pr diff --name-only (must match scope)
- gh pr checks --watch (or state “checks unavailable/pending”)

PR ID PROOF (required):
- gh pr view --json number,url,headRefName --jq '{number:.number,url:.url,branch:.headRefName}'

5) Cleanup always:
- rm -f pr_body.md pr_body_raw.md

──────────────────────────────────────────────────────────────────────────────
WORKTREE CLEANUP (always)

**WARNING:** Do NOT run `git checkout main` repeatedly in parallel runs - this causes branch conflicts between agents.

- Single-agent / non-parallel mode:
  - cd out of worktree (cd - or cd ..)
  - git worktree remove "$WT_DIR"
  - git worktree prune

PROOF REQUIRED:
- Paste final `git status -sb` output in your final response.

──────────────────────────────────────────────────────────────────────────────
FINAL RESPONSE FORMAT (Required)

Return exactly:
1) Branch name + commit SHA
2) PR URL + number (or “PR not created” + error summary)
3) Files changed/added
4) Minimal diff summary
5) Tests added/updated
6) Commands run + local/CI gate status (include validation proof snippet)
7) Scope exceptions (if any)
8) Confirmation workspace returned to clean main (include git status proof)
9) gh auth status result (OK / retried with ["all"] / failed)
10) “PR body validation passed ✅ (all template headers present)”
