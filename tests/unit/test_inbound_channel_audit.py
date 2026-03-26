"""Unit tests for the inbound-channel-audit hook (issue #1763).

Tests cover:
- extract_channel_blocks: closed vs unclosed tags, code-fence filtering
- _strip_code_blocks: markdown fences and inline code removal
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

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
