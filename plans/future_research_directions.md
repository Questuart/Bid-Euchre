# Future Research Directions

**Created:** 2026-03-18
**Context:** Brainstorm captured at the close of Arc D v2 lineage (R0–R3 complete).
These are potential follow-on directions — none are committed or prioritized.

---

## Evaluation & Benchmarking

### 1. Oracle / Perfect-Information Ceiling
Establish the theoretical maximum net_eppd by building an oracle bidder that
sees all four hands, enumerates every legal bid, simulates each with
GluttonStrategy, and picks the optimum. This gives an absolute ceiling so all
future results can be expressed as "X% of oracle" rather than relative-only
metrics. Dead simple experiment — could also compute a random-bidder floor to
define a normalized 0–100% scale.

### 2. Teacher → Train Style Evaluation
Use a strong model (GBT) as a teacher to evaluate or train weaker models.
Knowledge distillation, soft-label training, or using GBT's bid
probabilities as training signal for lighter architectures.

### 3. Cross-Rung H2H
Play rung models directly against each other (R0-GBT vs R3-GBT) rather than
only measuring deltas against the frozen anchor. Reveals whether rung
progression translates to direct competitive advantage.

### 4. Learning Curves / Dataset Scaling
Train the same models on 500 / 1K / 5K / 25K / 100K / 500K deals and plot
performance vs data size. Identifies diminishing returns and whether GBT or
OLS benefits more from additional data.

### 5. Seed Sensitivity Analysis
Run the same experiment with 10+ different seeds. Measure variance in model
rankings, hypothesis outcomes, and key metrics. Establishes how robust the
lineage findings are.

---

## Training Paradigms

### 6. Recursive Self-Improving Loop
Use the best trained model (GBT) as the continuation policy to generate
better training labels, then retrain. Iterate. Each cycle should produce
more accurate counterfactual outcome estimates, improving label quality.
Key question: does this converge, and how quickly?

### 7. Reinforcement Learning / Self-Play
Learn bidding policy directly through game outcomes (policy gradient,
Q-learning, PPO) rather than regression on counterfactual labels. A
fundamentally different training paradigm from the supervised approach used
in Arc D v2.

### 8. Fully "Learned" Model — No Hand-Crafted Features
End-to-end model that takes raw card representation (e.g., 40-dim binary
vector) and learns its own features. Neural net / transformer architecture.
Tests whether hand-crafted features are a ceiling or a shortcut.

### 9. CFR / Imperfect Information Game Solving
Counterfactual regret minimization (Libratus/Pluribus approach). Bid Euchre
is an imperfect information game; CFR is the purpose-built paradigm for
computing Nash equilibrium strategies in such games.

### 10. MCTS / Search-Based Bidding
Monte Carlo tree search — simulate many possible hand distributions before
making a bid. Computationally expensive but potentially stronger than
pattern-matching from features. Could also serve as a strong oracle for
generating training labels.

### 11. Imitation Learning from Human Play
Once the browser game collects human play data, learn from expert human
bidding decisions. Different from human calibration — this is using human
data as training signal, not just evaluation.

---

## Model Architecture & Composition

### 12. Ensemble Methods
Combine `full_ols_av` (best solo/comparator) and `gbt_av` (best H2H) into a
hybrid bidder. Weighted averaging, stacking, or routing based on hand
characteristics. The persistent comparator-vs-H2H divergence suggests
ensembling could capture both strengths.

### 13. Contract-Specific Specialist Models
The `full_ols_av` low-contract divergence (40.6% low bids vs others' 70–97%
suit) suggests that per-contract-type specialist models or a routing layer
could outperform a single universal bidder.

### 14. Alternative Architectures
Neural nets / transformers applied to card game features. Could be
structured (learned features + structured output) rather than pure
end-to-end. Attention mechanisms over cards or auction history.

### 15. Model Compression / Distillation
GBT is large; browser needs fast inference. Compress the best model into
something lightweight enough for real-time play (distillation into a smaller
net, pruning, quantization).

---

## Strategy & Game Play

### 16. Game-Level Strategy
Incorporate running score and match state into bidding decisions. Currently
excluded by design (Arc D v2 §2 — standalone hands only). A bidder that
adjusts aggression based on score differential, game phase, or match context.

### 17. Play Strategy Improvements
Improve trick play (card-by-card decisions during a hand) as opposed to
bidding strategy. GluttonStrategy is the current fixed trick player — better
play strategies would improve both real game performance AND the quality of
counterfactual training labels for bidding models.

### 18. Defensive Bidding
Bidding to block opponents rather than to win your own contract. Current
models optimize declaring-team net_points. Defensive sacrifice bids (taking
a contract you expect to partially set to prevent opponents from getting a
better one) are a different optimization target.

### 19. R4+ Card Inference
Inferring opponent holdings from auction bids (explicitly scoped as next
rung in governing plan §6.4.7). Would require new feature extraction and
likely a different model architecture. Distinct from trick-play card
counting.

---

## Multi-Agent & Game Theory

### 20. Partner Signaling / Cooperative Bidding
Partners developing learned communication through their bids (like bridge
conventions). Not just using partner features passively, but actively
encoding information in bid choices for the partner to decode. Two agents
learning to coordinate.

### 21. Opponent Modeling / Adaptation
Adjusting strategy based on observed opponent tendencies during a match.
Different from game-level strategy (score-based) and card inference
(hand-based). This is learning behavioral patterns of specific opponents.

### 22. Game-Theoretic / Mixed-Strategy Approaches
The persistent comparator-vs-H2H divergence (OLS best solo, GBT best
adversarial) suggests game-theoretic framing. Nash equilibrium bidding,
minimax, or mixed strategies that are robust against arbitrary opponents.

### 23. Uncertainty-Aware Bidding
A model that knows when it's uncertain and bids conservatively. Calibrated
confidence intervals on bid quality, not just point estimates. Bayesian
approaches or conformal prediction for bid decisions.

---

## Deployment & Data

### 24. Browser Game Integration
Using the best models as AI opponents in the browser game. Governed
separately by `plans/browser_game/governing_plan.md`. Includes difficulty
levels, real-time inference, and UX considerations.

### 25. Human Calibration
Once the browser game captures human play data, calibrate models against
human decision quality. Not just "do models beat humans" but "where do
models and humans disagree, and who is right?"

### 26. Rule Extraction / Learned Heuristics
Distill what the models learned back into human-usable bidding guidelines.
"GBT bids well" is useful for bots; "here are the 10 rules GBT follows" is
useful for human players. Decision boundary analysis, case studies of
interesting hands.
