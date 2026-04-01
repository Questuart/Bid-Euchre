#!/usr/bin/env python3
"""UserPromptSubmit hook: audit inbound <channel> tags and route ack commands.

When a Telegram message arrives via the plugin, it appears in the conversation
as a ``<channel source="telegram" chat_id="..." ...>body</channel>`` tag.
This hook intercepts those tags at the UserPromptSubmit seam and:

1. Calls ``audit_channel_tag()`` to durably record each inbound exchange.
2. Calls ``process_inbound_ack()`` to check if the message is an ack command
   (e.g. ``ack abc1``, ``dismiss xyz``, ``mute foo``, ``clear``).
3. If an ack command was detected, injects the reply text via
   ``additionalContext`` so the orchestrator sends confirmation back to
   Telegram.

Design constraints:
- Best-effort: audit/ack failures never block prompt submission.
- Fast guard in the bash wrapper skips Python entirely when no ``<channel``
  tag is present in the prompt (common case ~0ms).
- Uses ``uv run`` to access project imports (bid_euchre.ops).
- Lazy imports for project modules to keep the fast-exit path stdlib-only.

Closes #1752.  Part of #1826.
"""

from __future__ import annotations

import json
import re
import sys

# --- Tag extraction ----------------------------------------------------------

# Strip markdown code fences and neutralise inline code before scanning for
# channel tags.  This prevents pasted <channel> examples from being audited
# as real ingress while preserving backtick content inside real channel bodies.
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

# Attribute extraction for chat_id/message_id from tag text.
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _neutralise_inline_code(m: re.Match[str]) -> str:
    """Replace channel tag fragments inside inline code with safe tokens.

    The backtick delimiters and the rest of the span are preserved so that
    real channel bodies containing inline code (e.g. ``use `git status` ``)
    are not damaged.
    """
    span = m.group(0)
    if "<channel" in span:
        span = span.replace("<channel", "&lt;channel")
    if "</channel>" in span:
        span = span.replace("</channel>", "&lt;/channel&gt;")
    return span


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks and neutralise channel tags in inline code.

    Fenced blocks (triple-backtick) are removed entirely.  Inline backtick
    spans are *preserved* but any ``<channel`` or ``</channel>`` inside them
    is replaced with HTML-safe tokens so the tag regex will not match pasted
    examples or accidentally terminate a real channel body early, while the
    surrounding backtick content is kept intact for real channel bodies.
    """
    text = _CODE_FENCE_RE.sub("", text)
    return _INLINE_CODE_RE.sub(_neutralise_inline_code, text)


def extract_channel_blocks(text: str) -> list[tuple[str, str]]:
    """Return ``(tag_text, body)`` pairs for every ``<channel>`` block in *text*.

    Filters out:
    - Tags inside markdown code fences or inline code (pasted examples)
    - Unclosed tags (malformed or partial — could swallow remaining prompt)
    """
    cleaned = _strip_code_blocks(text)
    return [(m.group(1), m.group(2).strip()) for m in _CHANNEL_RE.finditer(cleaned)]


def _parse_tag_attrs(tag_text: str) -> dict[str, str]:
    """Extract ``key="value"`` attributes from a ``<channel ...>`` tag."""
    return dict(_ATTR_RE.findall(tag_text))


def _route_ack(body: str, tag_text: str) -> str | None:
    """Try to route *body* through :func:`process_inbound_ack`.

    Returns a formatted reply instruction string if the body was an ack command
    and produced a reply, or ``None`` otherwise.

    This function performs lazy imports to avoid loading project modules on the
    fast path.
    """
    from bid_euchre.ops.monitor import process_inbound_ack  # noqa: E402

    # Extract and validate chat_id before processing ack commands.
    # A missing or empty chat_id means the tag is malformed or synthetic —
    # we cannot route a reply without knowing the destination chat.
    attrs = _parse_tag_attrs(tag_text)
    chat_id = attrs.get("chat_id", "")
    if not chat_id:
        return None

    result = process_inbound_ack(body)
    if not result.is_ack_command or not result.reply_text:
        return None

    parts = [f"TELEGRAM ACK REPLY (chat_id={chat_id}):"]
    parts.append(result.reply_text)
    parts.append(f"→ Reply to Telegram chat {chat_id} with the above confirmation.")
    return "\n".join(parts)


def main() -> int:
    """Entry point.  Reads UserPromptSubmit JSON from stdin, audits and routes."""
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

    ack_replies: list[str] = []

    for tag_text, body in blocks:
        # --- Audit ---
        try:
            rec = audit_channel_tag(tag_text, body)
            if rec:
                print(
                    f"audit-inbound: {rec.exchange_id}",
                    file=sys.stderr,
                )
        except Exception:  # noqa: BLE001 — best-effort
            pass

        # --- Ack routing ---
        try:
            reply = _route_ack(body, tag_text)
            if reply:
                ack_replies.append(reply)
        except Exception:  # noqa: BLE001 — best-effort, never block prompt
            pass

    # If any ack commands were detected, inject reply instructions as
    # additionalContext so the orchestrator can relay confirmations.
    if ack_replies:
        context = "\n\n".join(ack_replies)
        print(json.dumps({"additionalContext": context}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
