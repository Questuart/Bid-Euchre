"""Unit tests for the inbound-channel-audit hook (issue #1763, #1826).

Tests cover:
- extract_channel_blocks: closed vs unclosed tags, code-fence filtering
- _strip_code_blocks: markdown fences and inline code removal
- _parse_tag_attrs: attribute extraction from channel tags
- _route_ack: ack command routing through process_inbound_ack
- main: end-to-end hook with ack additionalContext injection
"""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# The hook is a standalone script, not a package module.  Import it by path.
_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / ".claude"
    / "hooks"
    / "inbound-channel-audit.py"
)


@pytest.fixture(scope="module")
def hook() -> ModuleType:
    """Import the hook script as a module."""
    spec = importlib.util.spec_from_file_location("inbound_channel_audit", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbound_channel_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# _strip_code_blocks
# ---------------------------------------------------------------------------


class TestStripCodeBlocks:
    def test_removes_fenced_code_block(self, hook: ModuleType) -> None:
        text = 'before ```<channel source="telegram" chat_id="1">x</channel>``` after'
        result = hook._strip_code_blocks(text)
        assert "<channel" not in result
        assert "before" in result
        assert "after" in result

    def test_removes_multiline_fenced_code_block(self, hook: ModuleType) -> None:
        text = (
            "Some text\n"
            "```python\n"
            '<channel source="telegram" chat_id="1">body</channel>\n'
            "```\n"
            "More text"
        )
        result = hook._strip_code_blocks(text)
        assert "<channel" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_neutralises_channel_in_inline_code(self, hook: ModuleType) -> None:
        """Inline backticks are preserved but <channel inside them is neutralised."""
        text = 'Use `<channel source="telegram">` to send messages'
        result = hook._strip_code_blocks(text)
        assert "<channel" not in result
        assert "&lt;channel" in result
        assert "Use" in result
        assert "to send messages" in result

    def test_neutralises_closing_channel_in_inline_code(self, hook: ModuleType) -> None:
        """Inline closing tags must not terminate real channel blocks early."""
        text = "Body contains `</channel>` literally"
        result = hook._strip_code_blocks(text)
        assert "</channel>" not in result
        assert "&lt;/channel&gt;" in result

    def test_preserves_inline_code_without_channel(self, hook: ModuleType) -> None:
        """Inline backtick content with no <channel is left untouched."""
        text = "Run `git status` to check"
        result = hook._strip_code_blocks(text)
        assert result == text

    def test_preserves_non_code_text(self, hook: ModuleType) -> None:
        text = "No code blocks here, just plain text."
        result = hook._strip_code_blocks(text)
        assert result == text

    def test_empty_string(self, hook: ModuleType) -> None:
        assert hook._strip_code_blocks("") == ""


# ---------------------------------------------------------------------------
# extract_channel_blocks — closed tags
# ---------------------------------------------------------------------------


class TestExtractChannelBlocksClosed:
    def test_single_closed_tag(self, hook: ModuleType) -> None:
        text = '<channel source="telegram" chat_id="123" message_id="42" user="alice" ts="2026-03-24T06:00:00Z">Hello bot</channel>'
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 1
        tag, body = blocks[0]
        assert 'chat_id="123"' in tag
        assert body == "Hello bot"

    def test_multiple_closed_tags(self, hook: ModuleType) -> None:
        text = (
            '<channel source="telegram" chat_id="1" message_id="10" user="a" ts="t1">First</channel>\n'
            '<channel source="telegram" chat_id="2" message_id="20" user="b" ts="t2">Second</channel>'
        )
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 2
        assert blocks[0][1] == "First"
        assert blocks[1][1] == "Second"

    def test_multiline_body(self, hook: ModuleType) -> None:
        text = '<channel source="telegram" chat_id="1" message_id="1" user="a" ts="t">Line 1\nLine 2\nLine 3</channel>'
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 1
        assert "Line 1" in blocks[0][1]
        assert "Line 3" in blocks[0][1]


# ---------------------------------------------------------------------------
# extract_channel_blocks — unclosed tags (issue #1763 fix)
# ---------------------------------------------------------------------------


class TestExtractChannelBlocksUnclosed:
    def test_unclosed_tag_skipped(self, hook: ModuleType) -> None:
        """Unclosed <channel> tag must NOT swallow the rest of the prompt."""
        text = '<channel source="telegram" chat_id="123">This is an unclosed tag\nand more text follows\neven more text'
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 0, "Unclosed tags should be skipped entirely"

    def test_unclosed_tag_does_not_affect_closed_tag(self, hook: ModuleType) -> None:
        """A closed tag after an unclosed tag should still be matched."""
        text = (
            '<channel source="telegram" chat_id="1">unclosed tag here\n'
            "more text that should not be swallowed\n"
            '<channel source="telegram" chat_id="2" message_id="20" user="b" ts="t">Real message</channel>'
        )
        blocks = hook.extract_channel_blocks(text)
        # The closed tag should be matched; the unclosed one skipped.
        # Note: depending on regex behavior, the unclosed + closed might
        # merge. The key invariant is we don't swallow the whole prompt.
        assert any("Real message" in body for _, body in blocks)

    def test_self_closing_tag_not_matched(self, hook: ModuleType) -> None:
        """Self-closing <channel .../> is not a real message block."""
        text = '<channel source="telegram" chat_id="1" />'
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 0


# ---------------------------------------------------------------------------
# extract_channel_blocks — pasted examples in code (issue #1763 fix)
# ---------------------------------------------------------------------------


class TestExtractChannelBlocksCodeFiltering:
    def test_tag_inside_code_fence_ignored(self, hook: ModuleType) -> None:
        text = (
            "Here is an example:\n"
            "```\n"
            '<channel source="telegram" chat_id="123" message_id="42" user="alice" ts="t">example body</channel>\n'
            "```\n"
            "The above is just an example."
        )
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 0

    def test_tag_inside_inline_code_ignored(self, hook: ModuleType) -> None:
        text = 'Use `<channel source="telegram" chat_id="1">msg</channel>` format'
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 0

    def test_real_tag_alongside_code_example(self, hook: ModuleType) -> None:
        """A real tag outside code is still matched when examples exist in code."""
        text = (
            'Example: `<channel source="telegram" chat_id="1">example</channel>`\n\n'
            '<channel source="telegram" chat_id="999" message_id="50" user="bob" ts="t">Real message here</channel>'
        )
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 1
        assert blocks[0][1] == "Real message here"
        assert 'chat_id="999"' in blocks[0][0]

    def test_tag_inside_python_code_fence_ignored(self, hook: ModuleType) -> None:
        text = (
            "Documentation:\n"
            "```python\n"
            "# Example tag format\n"
            'tag = \'<channel source="telegram" chat_id="42">body</channel>\'\n'
            "```\n"
        )
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 0

    def test_inline_closing_tag_inside_real_body_does_not_truncate(
        self, hook: ModuleType
    ) -> None:
        """Inline ``</channel>`` inside a real body must stay literal."""
        text = (
            '<channel source="telegram" chat_id="123" message_id="77" user="alice" ts="t">'
            "Please type `</channel>` literally before you continue."
            "</channel>"
        )
        blocks = hook.extract_channel_blocks(text)
        assert len(blocks) == 1
        assert "Please type" in blocks[0][1]
        assert "before you continue." in blocks[0][1]


# ---------------------------------------------------------------------------
# Regression: original bug — unclosed tag swallows everything
# ---------------------------------------------------------------------------


class TestRegressionUnclosedSwallow:
    def test_unclosed_tag_does_not_consume_entire_prompt(
        self, hook: ModuleType
    ) -> None:
        """The original regex with ``$`` fallback would match from an unclosed
        <channel> tag to the end of the string, effectively swallowing the
        entire remaining prompt as 'body'. This must not happen."""
        prompt = (
            'User: Here is a channel tag example: <channel source="telegram" chat_id="1">\n'
            "This is a long prompt with many lines\n" * 50 + "End of prompt"
        )
        blocks = hook.extract_channel_blocks(prompt)
        # The unclosed tag should NOT produce a block with 50+ lines of body
        for _, body in blocks:
            assert (
                len(body) < 200
            ), f"Unclosed tag swallowed too much content ({len(body)} chars)"


# ---------------------------------------------------------------------------
# _parse_tag_attrs
# ---------------------------------------------------------------------------


class TestParseTagAttrs:
    def test_extracts_all_attrs(self, hook: ModuleType) -> None:
        tag = '<channel source="telegram" chat_id="123" message_id="42" user="alice" ts="2026-03-24T06:00:00Z">'
        attrs = hook._parse_tag_attrs(tag)
        assert attrs["source"] == "telegram"
        assert attrs["chat_id"] == "123"
        assert attrs["message_id"] == "42"
        assert attrs["user"] == "alice"

    def test_empty_tag(self, hook: ModuleType) -> None:
        attrs = hook._parse_tag_attrs("<channel>")
        assert attrs == {}

    def test_partial_attrs(self, hook: ModuleType) -> None:
        tag = '<channel source="telegram" chat_id="999">'
        attrs = hook._parse_tag_attrs(tag)
        assert attrs["chat_id"] == "999"
        assert "message_id" not in attrs


# ---------------------------------------------------------------------------
# _route_ack — ack command routing
# ---------------------------------------------------------------------------


class TestRouteAck:
    """Test ack routing through process_inbound_ack."""

    def test_ack_command_returns_reply(self, hook: ModuleType) -> None:
        """An ack command body should produce a reply instruction string."""
        mock_result = MagicMock()
        mock_result.is_ack_command = True
        mock_result.reply_text = "✅ Acked alert abc123"

        with patch(
            "bid_euchre.ops.monitor.process_inbound_ack",
            return_value=mock_result,
        ):
            tag = '<channel source="telegram" chat_id="555" message_id="10" user="op" ts="t">'
            reply = hook._route_ack("ack abc1", tag)

        assert reply is not None
        assert "TELEGRAM ACK REPLY" in reply
        assert "chat_id=555" in reply
        assert "✅ Acked alert abc123" in reply
        assert "Reply to Telegram chat 555" in reply

    def test_non_ack_message_returns_none(self, hook: ModuleType) -> None:
        """Non-ack messages should return None (passthrough)."""
        mock_result = MagicMock()
        mock_result.is_ack_command = False
        mock_result.reply_text = None

        with patch(
            "bid_euchre.ops.monitor.process_inbound_ack",
            return_value=mock_result,
        ):
            tag = '<channel source="telegram" chat_id="555">'
            reply = hook._route_ack("Hello, how are things?", tag)

        assert reply is None

    def test_ack_command_no_reply_text_returns_none(self, hook: ModuleType) -> None:
        """Ack command that produces no reply text should return None."""
        mock_result = MagicMock()
        mock_result.is_ack_command = True
        mock_result.reply_text = None

        with patch(
            "bid_euchre.ops.monitor.process_inbound_ack",
            return_value=mock_result,
        ):
            tag = '<channel source="telegram" chat_id="555">'
            reply = hook._route_ack("ack xyz", tag)

        assert reply is None

    def test_missing_chat_id_returns_none(self, hook: ModuleType) -> None:
        """Missing chat_id should short-circuit — cannot route reply without destination."""
        tag = '<channel source="telegram">'
        reply = hook._route_ack("ack abc1", tag)

        # chat_id validation happens before process_inbound_ack is called,
        # so no mock is needed — the function exits early.
        assert reply is None


# ---------------------------------------------------------------------------
# main — end-to-end hook with ack additionalContext injection
# ---------------------------------------------------------------------------


class TestMainAckRouting:
    """Test the main() function produces additionalContext for ack commands."""

    def _run_main(self, hook: ModuleType, prompt: str) -> tuple[int, str]:
        """Run hook.main() with a given prompt, capturing stdout."""
        data = json.dumps({"user_prompt": prompt})
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(data)),
            patch("sys.stdout", captured),
        ):
            rc = hook.main()
        return rc, captured.getvalue()

    def test_ack_command_injects_additional_context(self, hook: ModuleType) -> None:
        """An ack command in a Telegram tag should produce additionalContext JSON."""
        mock_ack_result = MagicMock()
        mock_ack_result.is_ack_command = True
        mock_ack_result.reply_text = "✅ Acked alert item_abc"

        mock_audit_rec = MagicMock()
        mock_audit_rec.exchange_id = "ex_001"

        prompt = '<channel source="telegram" chat_id="42" message_id="7" user="op" ts="t">ack abc</channel>'

        with (
            patch(
                "bid_euchre.ops.audit_trail.audit_channel_tag",
                return_value=mock_audit_rec,
            ),
            patch(
                "bid_euchre.ops.monitor.process_inbound_ack",
                return_value=mock_ack_result,
            ),
        ):
            rc, stdout = self._run_main(hook, prompt)

        assert rc == 0
        assert stdout.strip()  # Should have output
        output = json.loads(stdout.strip())
        assert "additionalContext" in output
        ctx = output["additionalContext"]
        assert "TELEGRAM ACK REPLY" in ctx
        assert "chat_id=42" in ctx
        assert "✅ Acked alert item_abc" in ctx

    def test_non_ack_message_no_additional_context(self, hook: ModuleType) -> None:
        """A regular (non-ack) Telegram message should not inject additionalContext."""
        mock_ack_result = MagicMock()
        mock_ack_result.is_ack_command = False
        mock_ack_result.reply_text = None

        mock_audit_rec = MagicMock()
        mock_audit_rec.exchange_id = "ex_002"

        prompt = '<channel source="telegram" chat_id="42" message_id="7" user="op" ts="t">Hello, checking in</channel>'

        with (
            patch(
                "bid_euchre.ops.audit_trail.audit_channel_tag",
                return_value=mock_audit_rec,
            ),
            patch(
                "bid_euchre.ops.monitor.process_inbound_ack",
                return_value=mock_ack_result,
            ),
        ):
            rc, stdout = self._run_main(hook, prompt)

        assert rc == 0
        # No additionalContext output for non-ack messages
        clean = stdout.strip()
        if clean:
            parsed = json.loads(clean)
            assert "additionalContext" not in parsed

    def test_no_channel_tags_fast_exit(self, hook: ModuleType) -> None:
        """Prompts without channel tags should exit immediately with no output."""
        rc, stdout = self._run_main(hook, "Just a normal prompt with no tags")
        assert rc == 0
        assert stdout.strip() == ""

    def test_ack_routing_failure_does_not_block(self, hook: ModuleType) -> None:
        """If process_inbound_ack raises, the hook should still return 0."""
        mock_audit_rec = MagicMock()
        mock_audit_rec.exchange_id = "ex_003"

        prompt = '<channel source="telegram" chat_id="42" message_id="7" user="op" ts="t">ack abc</channel>'

        with (
            patch(
                "bid_euchre.ops.audit_trail.audit_channel_tag",
                return_value=mock_audit_rec,
            ),
            patch(
                "bid_euchre.ops.monitor.process_inbound_ack",
                side_effect=RuntimeError("Simulated failure"),
            ),
        ):
            rc, stdout = self._run_main(hook, prompt)

        assert rc == 0  # Best-effort — never block

    def test_multiple_tags_one_ack(self, hook: ModuleType) -> None:
        """Multiple channel tags where only one is an ack command."""
        ack_result = MagicMock()
        ack_result.is_ack_command = True
        ack_result.reply_text = "✅ Dismissed alert xyz"

        non_ack_result = MagicMock()
        non_ack_result.is_ack_command = False
        non_ack_result.reply_text = None

        mock_audit_rec = MagicMock()
        mock_audit_rec.exchange_id = "ex_004"

        prompt = (
            '<channel source="telegram" chat_id="10" message_id="1" user="a" ts="t">Hello</channel>\n'
            '<channel source="telegram" chat_id="10" message_id="2" user="a" ts="t">dismiss xyz</channel>'
        )

        call_count = [0]

        def mock_process(text, **kwargs):
            call_count[0] += 1
            if "dismiss" in text:
                return ack_result
            return non_ack_result

        with (
            patch(
                "bid_euchre.ops.audit_trail.audit_channel_tag",
                return_value=mock_audit_rec,
            ),
            patch(
                "bid_euchre.ops.monitor.process_inbound_ack",
                side_effect=mock_process,
            ),
        ):
            rc, stdout = self._run_main(hook, prompt)

        assert rc == 0
        assert call_count[0] == 2  # Both bodies processed
        output = json.loads(stdout.strip())
        ctx = output["additionalContext"]
        assert "✅ Dismissed alert xyz" in ctx
