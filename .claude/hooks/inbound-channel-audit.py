#!/usr/bin/env python3
"""UserPromptSubmit hook: audit inbound <channel> tags to the audit trail.

When a Telegram message arrives via the plugin, it appears in the conversation
as a ``<channel source="telegram" chat_id="..." ...>body</channel>`` tag.
This hook intercepts those tags at the UserPromptSubmit seam and calls
``audit_channel_tag()`` to durably record each inbound exchange.

Design constraints:
- Best-effort: audit failures never block prompt submission.
- Fast guard in the bash wrapper skips Python entirely when no ``<channel``
  tag is present in the prompt (common case ~0ms).
- Uses ``uv run`` to access project imports (bid_euchre.ops.audit_trail).

Closes #1752.
"""

from __future__ import annotations

import json
import re
import sys

# --- Tag extraction ----------------------------------------------------------

# Strip markdown code fences and inline code before scanning for channel tags.
# This prevents pasted <channel> examples from being audited as real ingress.
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")

# Only match properly closed <channel ...>body</channel> blocks.
# Real Telegram plugin messages always include the closing tag.
# Unclosed tags are skipped to prevent swallowing the rest of the prompt
# (the old regex used ``$`` as a fallback, which with re.DOTALL could
# consume everything after an unclosed tag — see #1763).
_CHANNEL_RE = re.compile(
    r"(<channel\s[^>]*>)(.*?)</channel>",
    re.DOTALL,
)


def _strip_code_blocks(text: str) -> str:
    """Remove markdown code fences and inline code spans from *text*.

    Returns the text with code blocks replaced by empty strings so that
    ``<channel>`` tags pasted as examples inside code are not matched.
    """
    text = _CODE_FENCE_RE.sub("", text)
    return _INLINE_CODE_RE.sub("", text)


def extract_channel_blocks(text: str) -> list[tuple[str, str]]:
    """Return ``(tag_text, body)`` pairs for every ``<channel>`` block in *text*.

    Filters out:
    - Tags inside markdown code fences or inline code (pasted examples)
    - Unclosed tags (malformed or partial — could swallow remaining prompt)
    """
    cleaned = _strip_code_blocks(text)
    return [(m.group(1), m.group(2).strip()) for m in _CHANNEL_RE.finditer(cleaned)]


def main() -> int:
    """Entry point.  Reads UserPromptSubmit JSON from stdin, audits channel tags."""
    raw = sys.stdin.read()
    if not raw:
        return 0

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return 0

    prompt: str = data.get("user_prompt", "")
    if not prompt or "<channel" not in prompt:
        return 0

    blocks = extract_channel_blocks(prompt)
    if not blocks:
        return 0

    # Import only when we actually need to audit — keeps the fast-exit path
    # free of project imports.
    from bid_euchre.ops.audit_trail import audit_channel_tag  # noqa: E402

    for tag_text, body in blocks:
        try:
            rec = audit_channel_tag(tag_text, body)
            if rec:
                print(
                    f"audit-inbound: {rec.exchange_id}",
                    file=sys.stderr,
                )
        except Exception:  # noqa: BLE001 — best-effort
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
