# External Signal Sources (external_signal_sources.md)

> Operator-curated list of external sources to monitor for signals that
> would affect the steward platform (Claude Code changelogs, Anthropic
> API updates, tmux/terminal upstream, GitHub Actions features). Seed
> location per §14 open item 17 of the governing plan; promoted to KB
> by Primitive C Phase 0.
>
> **Commit policy (ADR 010):** tracked; operator-gated additions.
>
> **Schema:** each entry is a `### <source name>` heading followed by:
>
> - **URL / RSS:** canonical location (link or feed URL)
> - **Cadence:** how often to check (e.g., weekly, on release)
> - **Triggers a KB update when:** condition that would require lesson
>   capture (e.g., "permission-mode semantics change")
> - **Owner:** which lane / operator role watches this source

---

## Seed entries

### Claude Code release notes

**URL / RSS:** https://docs.anthropic.com/en/docs/claude-code/changelog
(plus Anthropic status page for incident/outage signals)

**Cadence:** weekly (orchestrator `/check-in` cron), and on any
operator-triggered `/run-changelog-review` invocation

**Triggers a KB update when:** auto-mode behavior changes; hook
lifecycle changes; tool-schema changes; session-lifetime or output-size
limit changes

**Owner:** orchestrator (via changelog-review skill, per Primitive D)

### Anthropic SDK changelog

**URL / RSS:** https://github.com/anthropics/anthropic-sdk-python/releases

**Cadence:** on release, checked by ops lane during monthly review

**Triggers a KB update when:** prompt-caching semantics change;
streaming event schema changes; tool-use block format changes

**Owner:** ops lane (reviews during Primitive A trace-schema evolution)

### tmux upstream

**URL / RSS:** https://github.com/tmux/tmux/releases

**Cadence:** on major release (3.x → 4.x); otherwise only if
`send-keys` or paste-bracketing behavior appears to drift

**Triggers a KB update when:** `send-keys` semantics change;
bracketed-paste escapes change; pane-content capture format changes

**Owner:** ops lane; monitors via brittleness-signal drift in
`harness_assumptions.md` entries citing tmux

### GitHub Actions features

**URL / RSS:** https://github.blog/changelog/label/actions/

**Cadence:** weekly scan

**Triggers a KB update when:** `dorny/paths-filter` is superseded;
required-status-check semantics change; branch-protection API changes

**Owner:** ops lane
