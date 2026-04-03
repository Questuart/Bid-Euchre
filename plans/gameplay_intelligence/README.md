# Claude Gameplay Intelligence

> Persistent knowledge base for Claude's gameplay testing, strategy analysis,
> and bug discovery. Updated every time Claude plays the game.

## Purpose

This directory is Claude's durable memory for gameplay sessions. Every time
Claude plays Bid Euchre (via Playwright, httpx, or any other method), it
should read this directory first and update it after.

## Files

| File | Purpose |
|------|---------|
| `bugs.md` | Gameplay bugs discovered during play — categorized, with repro steps |
| `strategy_observations.md` | Observations about AI bot play patterns, weaknesses, strengths |
| `play_techniques.md` | Bidding and card play techniques Claude has learned |
| `research_ideas.md` | Ideas for new strategies, experiments, or improvements |
| `session_log.md` | Per-session summaries — date, games played, results, key findings |

## Usage Protocol

### Before Playing
1. Read `session_log.md` for recent context
2. Read `bugs.md` to know what to watch for
3. Read `strategy_observations.md` for current AI behavior understanding

### During Play
- Note any bugs or unexpected behavior
- Observe AI card selection patterns
- Try different bidding approaches and note results

### After Playing
1. Append to `session_log.md` with date, games, results, findings
2. Update `bugs.md` with any new bugs (or mark fixed ones)
3. Update `strategy_observations.md` with new patterns observed
4. Add to `play_techniques.md` if you learned something about effective play
5. Add to `research_ideas.md` if you have ideas for strategy improvements
