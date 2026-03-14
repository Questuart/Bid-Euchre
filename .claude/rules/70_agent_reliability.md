# Agent Reliability — Context Window Constraints

> Spawned agents silently die when they exhaust their context window.
> This is a platform constraint, not a bug. Mitigate operationally.

## Failure Pattern

| Agent Duration | Output Size | Reliability |
|---------------|-------------|-------------|
| < 10 min, < 500KB | — | Reliable |
| 10-15 min, 500-700KB | — | Moderate risk |
| > 15 min or > 700KB | — | High risk of silent death |

## Rules

1. **One concept per agent.** Never combine unrelated tasks.
2. **Never include experiment/SMOKE runs in fix agents.** Run validation separately.
3. **Cap file reads.** Use offset/limit for large files. Avoid reading >5 large files.
4. **Prefer small sequential agents over large combined agents.**
5. **Keep prompts focused.** Don't include full code implementations in prompts.

## Detection

```bash
wc -c < /path/to/agent.output && sleep 5 && wc -c < /path/to/agent.output
# If identical = agent is dead
```

## Recovery

state.json + fingerprinting enables idempotent respawn. Respawn with tighter scope.

## Anti-Patterns

- "Fix bug AND run SMOKE AND update docs" in one agent
- Reading entire governing plan (2800 lines) into agent context
- Combining two independent PRs into one agent
- Waiting indefinitely without checking output growth
