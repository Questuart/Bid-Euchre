# PR Prompt Templates (Robust, Parallel-Safe)

These templates are designed for **cheap agents** operating in a repo with strict determinism + reproducibility requirements, and for **parallel** PR execution without scope leaks.

## 🚨 DEFAULT: Full Permissions Mode (CRITICAL)

**Run ALL PR agents in full permissions mode by default** (Cursor: `required_permissions: ["all"]`).

**WHY THIS IS CRITICAL**: macOS TLS/keychain sandbox issues (e.g., `OSStatus -26276`, certificate verification failures) prevent reliable GitHub API access via `gh` in restricted sandbox modes. Full permissions mode ensures TLS certificate validation works reliably for all `gh` commands.

---

## 🔐 GitHub Authentication in Cursor's Sandbox

Cursor runs commands in a sandboxed environment that **cannot access the macOS keychain**. This means:
- `gh auth status` may work in your regular terminal but fail inside Cursor
- The `gh` CLI's default keychain-based auth is blocked by the sandbox

### Symptoms of this issue

```
github.com
  X Failed to log in to github.com using token (GH_TOKEN)
  - The token in GH_TOKEN is invalid.
```

...even though `gh auth status` works in your regular terminal.

### Solution: Set GH_TOKEN explicitly

The sandbox CAN read environment variables. Set `GH_TOKEN` in your shell profile:

1. **Generate a personal access token** at https://github.com/settings/tokens/new
   - Required scopes: `repo`, `workflow`
   - Recommended: 90-day expiration

2. **Add to `~/.zshrc`** (or `~/.bashrc`):
   ```bash
   export GH_TOKEN="ghp_your_token_here"
   export GITHUB_TOKEN="$GH_TOKEN"
   ```

3. **Restart Cursor completely** (not just reload window)

### Debugging auth issues

Run these commands to diagnose:

```bash
# Check if token is set
echo "GH_TOKEN set: ${GH_TOKEN:+yes}"
echo "Token length: ${#GH_TOKEN}"

# Test in restricted sandbox (will likely fail)
gh auth status  # with required_permissions: ["network"]

# Test outside sandbox (should work if token is valid)
gh auth status  # with required_permissions: ["all"]
```

If the token works with `["all"]` but not `["network"]`, the sandbox is blocking keychain access. This is expected - use `["all"]` for all `gh` commands.

### Token expiration

If auth suddenly stops working after previously working:
1. Your token likely expired
2. Generate a new token and update `~/.zshrc`
3. Restart Cursor

---

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

## WORKTREE ENFORCEMENT (HARD GATE)

**Worktrees are MANDATORY. Branch-only workflows are FORBIDDEN.**

**Rationale:**
- Multiple agents switching branches in the same working directory causes accidental commits to `main` or to the wrong branch.
- Worktrees isolate each agent in its own directory, eliminating branch-switch races.
- Even single-agent runs MUST use worktrees to prevent accidental commits to `main`.

**FORBIDDEN COMMANDS:**
- `git checkout -b <branch>`
- `git switch -c <branch>`
- Committing from the main repo directory

**PROOF REQUIRED BEFORE ANY EDITS:**
You MUST run and paste the following outputs BEFORE making any file changes:
- `pwd`
- `git rev-parse --show-toplevel`
- `git worktree list`
- `git status`

**STOP CONDITION:** If you start editing files before showing proof that you are in a worktree, you MUST stop and restart.

## Worktree Setup (MANDATORY) — Copy/Paste Block

Use this exact setup for every PR. Do NOT improvise or use branch-only workflows.

```bash
git fetch origin
BRANCH="<fill_me>"
SUFFIX="$(date +%Y%m%d-%H%M%S)-$$"
WT="../.worktrees/${BRANCH//\//-}-$SUFFIX"
mkdir -p ../.worktrees
git worktree add -b "$BRANCH" "$WT" origin/main
cd "$WT"

# PROOF (paste outputs)
pwd
git rev-parse --show-toplevel
git worktree list
git status
```

**Note:** `gh` still requires HTTPS/TLS even if `git` uses SSH for transport.

## Local execution note (Cursor)

These prompts assume the agent runs in **Cursor's local terminal** (commands execute on the local machine).

**⚠️ Cursor's sandbox blocks keychain access.** See "GitHub Authentication in Cursor's Sandbox" section above for setup instructions.

To make PR creation reliable:
- `GH_TOKEN` must be set explicitly in `~/.zshrc` (keychain auth won't work in sandbox).
- Use `required_permissions: ["all"]` for all `gh` commands.
- `gh api user -q .login` must succeed (non-interactive).
- `git ls-remote origin HEAD` must succeed (non-interactive).
- `git remote -v` must show SSH for origin (`git@github.com:...`).

**SSH vs HTTPS clarification**:
- `git` uses the origin remote protocol (SSH or HTTPS).
- `gh` uses HTTPS API regardless.
- SSH fixes `git` transport, but `gh` still requires TLS certificate validation.
- Therefore: SSH does NOT replace TLS requirements for `gh` commands.

---

## Comprehension plan (no user confirmation required)

**Before editing any files, the agent must write:**
- 2–3 sentences describing what the PR will change
- the exact file list it expects to touch
- how it will verify (commands/tests)

Explicitly state: **do not ask the user to confirm; proceed after writing the plan.**

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
- Task is not complete until a PR URL is produced.
- If PR creation fails after one remediation retry, STOP and report (do not claim a PR exists without a URL).
- FINAL RESPONSE must include validation proof + PR body header validation + clean workspace proof.
- Paste terminal outputs **verbatim** when asked (do not summarize).

PARALLEL-SAFE RULES
- Do not touch shared/central files unless explicitly scoped.
- If you discover required changes outside scope that touch shared files: STOP and report.
- Do not “fix” nearby lint/docs unless it is strictly required for the scoped change.

## Dependency ordering / parallelism

If PR B depends on PR A, the prompt must say **"A must land before B starts"**

If PRs can be parallelized, the prompt must include:
- a non-overlapping file/area split
- explicit warning about conflict risk when touching the same emitter/runner/core file

GIT HYGIENE (required)
- Never work or commit on main.
- **Worktrees required; prove with commands before any edits.**
- Do NOT use `git checkout -b` or `git switch -c` from the main repo directory.
- Stage explicitly (no `git add .`).
- Single commit per PR.
- Clean up worktree at the end (see worktree cleanup section).

## Pre-commit hook recovery protocol

Recommended: run `pre-commit run -a` before commit if available.

If a commit fails because hooks modified files:
```bash
git status
git add -A
git commit -m "<same message>"
```

**Never use `--no-verify`** unless explicitly instructed.
Mention typical auto-fixers (EOF/whitespace, YAML, ruff) briefly.

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

## Expected outcomes checksum

Expected files changed (explicit list)
Expected tests changed (approx: "+2 tests", "no removals")
Expected behavior changes (1–2 bullets)

This is for self-audit; not a hard guarantee.

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
- Worktree creation (MANDATORY; branch-only workflows are forbidden):
  - Do NOT branch-switch from the shared checkout.
  - Worktree creation (from the main repo root):
    - BRANCH="<branch-name>"
    - SUFFIX="$(date +%Y%m%d-%H%M%S)-$$"
    - WT_DIR="../.worktrees/${BRANCH//\//-}-$SUFFIX"
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

**Shared file lock check (machine-checkable):**
```bash
SHARED_REGEX='^(pyproject\.toml|Makefile|\.github/|docs/02_agent/PR_PROMPT_TEMPLATES\.md|AGENTS\.md|scripts/lint_repo\.py)$'
git diff --name-only origin/main...HEAD | rg -n "$SHARED_REGEX" && echo "SHARED FILE TOUCHED ❌" && exit 1 || echo "No shared files ✅"
```

If a PR touches shared files, the prompt must explicitly scope them; otherwise STOP.

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

HARD GATES:
- Task is not complete until a PR URL is produced and cited below.
- If PR creation fails after one remediation retry, STOP and report (do not claim a PR exists without a URL).

Branch context gate (required):
- test "$(git branch --show-current)" != "main" && echo "On feature branch ✅" || (echo "On main ❌" && exit 1)

Primary PR path (gold path):
1) BRANCH="$(git branch --show-current)"
   gh pr create --base main --head "$BRANCH" --title "<PR Title>" --body-file pr_body.md
2) If `gh pr create` fails:
   - Do ONE remediation attempt (fix auth/token/permissions; required_permissions: ["all"]).
   - Retry `gh pr create` once.
   - If it still fails for a non-TLS/auth reason: STOP and report.
3) If PR was created successfully:
   - gh pr diff --name-only (must match scope)
   - gh pr checks --watch (or state “checks unavailable/pending”)

Fallback (TLS/auth edge case):
- Primary path is `gh pr create ... --body-file pr_body.md`.
- If TLS/auth prevents creation even after remediation and retry, run:
  `scripts/create_pr_curl.sh "<PR Title>" pr_body.md main`
- The script must print a PR URL. If the script is missing or does not produce the URL, STOP and report (do not invent a new script).
- If the fallback succeeds, treat it as the PR creation step above and continue with proof/cleanup.
- Manual PR mode is not allowed unless explicitly requested by the user.
- Manual PR mode is not allowed unless explicitly requested by the user.

PR ID PROOF (required):
- gh pr view --json number,url,headRefName --jq '{number:.number,url:.url,branch:.headRefName}'
- Final response must include the PR URL produced here.

Cleanup always:
- rm -f pr_body.md pr_body_raw.md

────────────────────────────────────────
Worktree cleanup (MUST)

**WARNING:** Do NOT run `git checkout main` repeatedly in parallel runs - this causes branch conflicts between agents.

**HARD GATE: PR URL before cleanup**
Do not remove the worktree unless a PR URL exists OR a STOP condition applied.

To prove PR exists, run:
```bash
gh pr view --json number,url,headRefName --jq '{number:.number,url:.url,branch:.headRefName}'
```

If this command fails and STOP conditions don't apply, do not cleanup; report failure.

Cleanup steps:
- cd .. (return to parent directory)
- git worktree remove "$WT"
- git worktree prune

PROOF REQUIRED:
- Paste the final `git worktree list` and `git status -sb` outputs.

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
- Task is not complete until a PR URL is produced.
- If PR creation fails after one remediation retry, STOP and report (do not claim a PR exists without a URL).
- FINAL RESPONSE must include validation proof + PR body header validation + clean workspace proof.
- Paste terminal outputs **verbatim** when asked (do not summarize).

PARALLEL-SAFE RULES
- Hard scope is a lock. Do not touch shared files outside scope.
- Do not edit central/index files unless explicitly scoped (README, docs/README.md, AGENTS.md, pyproject.toml, Makefile).
- If required change touches shared files outside scope: STOP and report.

## Dependency ordering / parallelism

If PR B depends on PR A, the prompt must say **"A must land before B starts"**

If PRs can be parallelized, the prompt must include:
- a non-overlapping file/area split
- explicit warning about conflict risk when touching the same emitter/runner/core file

GIT HYGIENE (required)
- Do not work or commit on main.
- **Worktrees required; prove with commands before any edits.**
- Do NOT use `git checkout -b` or `git switch -c` from the main repo directory.
- Stage explicitly (no git add .) and only within scope.
- Single commit per PR unless explicitly instructed otherwise.
- Push branch and create a PR (gh preferred).
- PR body MUST use .github/pull_request_template.md (prepend summary bullets).
- Default to creating the PR automatically via gh.
- Clean up worktree at the end (see worktree cleanup section).

## Pre-commit hook recovery protocol

Recommended: run `pre-commit run -a` before commit if available.

If a commit fails because hooks modified files:
```bash
git status
git add -A
git commit -m "<same message>"
```

**Never use `--no-verify`** unless explicitly instructed.
Mention typical auto-fixers (EOF/whitespace, YAML, ruff) briefly.

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

## Expected outcomes checksum

Expected files changed (explicit list)
Expected tests changed (approx: "+2 tests", "no removals")
Expected behavior changes (1–2 bullets)

This is for self-audit; not a hard guarantee.

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
- Worktree creation (MANDATORY for all runs, including single-agent):
  - Do NOT branch-switch the shared checkout.
  - Worktree creation (from the main repo root):
    - BRANCH="<branch-name>"
    - SUFFIX="$(date +%Y%m%d-%H%M%S)-$$"
    - WT_DIR="../.worktrees/${BRANCH//\//-}-$SUFFIX"
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

**Shared file lock check (machine-checkable):**
```bash
SHARED_REGEX='^(pyproject\.toml|Makefile|\.github/|docs/02_agent/PR_PROMPT_TEMPLATES\.md|AGENTS\.md|scripts/lint_repo\.py)$'
git diff --name-only origin/main...HEAD | rg -n "$SHARED_REGEX" && echo "SHARED FILE TOUCHED ❌" && exit 1 || echo "No shared files ✅"
```

If a PR touches shared files, the prompt must explicitly scope them; otherwise STOP.

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

HARD GATES:
- Task is not complete until a PR URL is produced and cited below.
- If PR creation fails after one remediation retry, STOP and report (do not claim a PR exists without a URL).

Branch context gate (required):
- test "$(git branch --show-current)" != "main" && echo "On feature branch ✅" || (echo "On main ❌" && exit 1)

Primary PR path (gold path):
1) BRANCH="$(git branch --show-current)"
   gh pr create --base main --head "$BRANCH" --title "<PR Title>" --body-file pr_body.md
2) If `gh pr create` fails:
   - Do ONE remediation attempt (fix auth/token/permissions; required_permissions: ["all"]).
   - Retry `gh pr create` once.
   - If it still fails for a non-TLS/auth reason: STOP and report.
3) If PR was created successfully:
   - gh pr diff --name-only (must match scope)
   - gh pr checks --watch (or state “checks unavailable/pending”)

Fallback (TLS/auth edge case):
- Primary path is `gh pr create ... --body-file pr_body.md`.
- If TLS/auth prevents creation even after remediation and retry, run:
  `scripts/create_pr_curl.sh "<PR Title>" pr_body.md main`
- The script must print a PR URL. If the script is missing or does not produce the URL, STOP and report (do not invent a new script).
- If the fallback succeeds, treat it as the PR creation step above and continue with proof/cleanup.

PR ID PROOF (required):
- gh pr view --json number,url,headRefName --jq '{number:.number,url:.url,branch:.headRefName}'
- Final response must include the PR URL produced here.

Cleanup always:
- rm -f pr_body.md pr_body_raw.md

──────────────────────────────────────────────────────────────────────────────
WORKTREE CLEANUP (always)

**WARNING:** Do NOT run `git checkout main` repeatedly in parallel runs - this causes branch conflicts between agents.

**HARD GATE: PR URL before cleanup**
Do not remove the worktree unless a PR URL exists OR a STOP condition applied.

To prove PR exists, run:
```bash
gh pr view --json number,url,headRefName --jq '{number:.number,url:.url,branch:.headRefName}'
```

If this command fails and STOP conditions don't apply, do not cleanup; report failure.

Cleanup steps:
- cd .. (return to parent directory)
- git worktree remove "$WT"
- git worktree prune

PROOF REQUIRED:
- Paste final `git worktree list` and `git status -sb` outputs.

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
