# Research Ideas — From Gameplay Observations

## Strategy Improvements

### 1. Card Conservation Logic
The biggest win for AI play. Current Glutton always plays highest. Should:
- Play lowest when trick is unwinnable
- Play lowest when partner is already winning
- Only play highest when you can actually take the trick
- **Impact:** Would dramatically reduce AI "throwing away" bowers and aces

### 2. Partner-Aware Play
AI treats all other players the same. Should:
- Recognize when partner is winning the trick (don't overthrow)
- Lead to partner's known strong suit
- Signal suit strength through play choices

### 3. Trump Management
AI burns all trump immediately. Should:
- Count remaining trump in the hand
- Save trump for critical tricks
- Lead trump strategically to draw out opponents' trump

### 4. Bidding Calibration
Current bidding models may be miscalibrated for the card play changes.
After fixing Glutton strategy:
- Re-run baseline experiments to see if win rates change
- Recalibrate bid thresholds if card play is now stronger/weaker

## Experiment Ideas

### A. Before/After Glutton Fix Comparison
- Run 1000 games with old Glutton (seed 42)
- Run 1000 games with fixed Glutton (same seed)
- Compare: win rates, avg margin, tricks won per hand, bower retention

### B. Card Conservation Impact Study
- Variant 1: Always play highest (current)
- Variant 2: Play lowest when can't win (basic conservation)
- Variant 3: Partner-aware (don't overthrow partner)
- Compare all three across 5000 games

### C. Human vs AI Play Style Analysis
- Once enough human games are played on Render, compare human play
  patterns to AI patterns
- Which cards do humans conserve that AI doesn't?
- Do humans bid differently than the models?
