# Plan Init - Code-First Planning

Create implementation plans grounded in actual source code, not assumptions.

## Core Principle

**Never guess at API signatures, function names, or import paths.** Always verify against real code before writing plans.

## Workflow

1. **Read the actual source files** involved in the planned changes
   - Locate all relevant modules, classes, and functions
   - Verify exact function signatures and parameter names
   - Check class hierarchies and inheritance
   - Confirm import paths and module structure

2. **Document verified details** in the plan
   - Reference exact file paths (e.g., `src/bid_euchre/strategy/bidding.py:142`)
   - Include actual function signatures from the code
   - Note any constraints or patterns discovered
   - List related files that may need updates

3. **Write the plan** using confirmed information
   - Use exact names from the codebase
   - Reference specific line numbers where helpful
   - Note any gaps or unknowns explicitly
   - Ask clarifying questions about scope before proceeding

## Anti-Patterns to Avoid

❌ Guessing function signatures based on naming conventions
❌ Assuming parameter names without checking
❌ Planning changes to code you haven't read
❌ Referencing utilities that may not exist

## Usage

Invoke with `/plan_init` when starting any multi-file or architectural planning task. This skill ensures your plan is grounded in reality, reducing revision cycles.

## Example Output Format

```markdown
## Implementation Plan: [Feature Name]

### Files to Modify
- `src/module/file.py:123` - `ClassName.method_name(param1: Type, param2: Type) -> ReturnType`
- `tests/unit/test_file.py` - Add test for new behavior

### Verified Constraints
- Current function signature: [exact signature from code]
- Calling locations: [list of files that call this function]
- Import structure: [current import pattern]

### Proposed Changes
[Detailed steps using exact names and paths verified above]
```

## Notes

- This skill is especially important for multi-PR architecture plans
- Always pair with asking clarifying scope questions
- Save plans to `plans/` directory as specified in CLAUDE.md
