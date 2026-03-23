# Browser Game Hosting and Human Data Capture — Amendments

**Governing plan:** `plans/browser_game/governing_plan.md`
**Last updated:** 2026-03-23 (V1 model-serving contract)

---

## BG-1 — V1 model serving narrowed to config-backed startup preload (2026-03-23)

**PR:** pending follow-up

**What changed:**
1. **V1 launch roster narrowed** — `heuristic` remains always available and
   `hybrid_olsa` is the only artifact-backed bidder in V1 when its configured
   artifact path exists. `gbt_action_value` is explicitly deferred until
   post-MVP.
2. **"Model registry" clarified** — For V1, the governing plan's roster
   language is satisfied by a config-backed approved model roster in
   `web/config.py` and `web/ai_manager.py`, not by a mutable database
   `model_registry` table.
3. **Startup preload required** — Approved bidder instances are loaded once
   during FastAPI startup and stored in `app.state`. Route handlers must only
   look up a cached model by `ai_model` id; they must not load artifacts per
   request, per turn, or per seat.
4. **Match persistence simplified** — Hosted-play persistence stores the
   selected `ai_model` id on each match. Artifact paths and bidder instances
   stay in config/runtime state, not in persisted match rows.
5. **Default launch path clarified** — `hybrid_olsa` is the default
   artifact-backed launch option, with `heuristic` as the guaranteed fallback
   when no approved artifact path is configured.

**Rationale:**
Local measurements taken on 2026-03-23 showed that `HybridOLSaBidder` is
effectively free to load after import and runs at roughly `0.3 ms` per bid on
the development machine, while `GBTActionValueBidder` adds materially more
cold-start and runtime complexity. For the V1 browser game, the main product
risk is startup/restart operational overhead, not steady-state bid latency.
Narrowing the launch roster to `heuristic` plus `hybrid_olsa` keeps the
hosted product simpler while preserving a clean upgrade path for more complex
models later.
