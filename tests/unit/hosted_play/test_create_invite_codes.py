"""Tests for scripts/internal/create_invite_codes.sh argument handling.

Validates that the script passes arguments via sys.argv rather than
shell interpolation, which is vulnerable to injection and breaks on
special characters (e.g., single quotes in labels).
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "internal"
    / "create_invite_codes.sh"
)


class TestCreateInviteCodesScript:
    """Validate script structure without executing it."""

    def test_script_exists(self):
        assert SCRIPT_PATH.exists(), f"Script not found: {SCRIPT_PATH}"

    def test_uses_sys_argv_not_shell_interpolation(self):
        """The Python code inside the script must use sys.argv, not ${VAR}."""
        content = SCRIPT_PATH.read_text()

        # The inline Python block should reference sys.argv for count and label
        assert "sys.argv[1]" in content, "Script should use sys.argv[1] for count"
        assert "sys.argv[2]" in content, "Script should use sys.argv[2] for label"

        # The Python code block (between the uv run python -c " and closing ")
        # should NOT contain ${COUNT} or ${LABEL} — those belong outside the
        # Python string as shell arguments.
        #
        # Split on 'uv run python -c "' to isolate the Python code block.
        parts = content.split('uv run python -c "')
        assert len(parts) == 2, "Expected exactly one inline Python block"
        python_block = parts[1].split('"')[0]  # up to closing "

        assert (
            "${COUNT}" not in python_block
        ), "Python code should not use ${COUNT} shell interpolation"
        assert (
            "${LABEL}" not in python_block
        ), "Python code should not use ${LABEL} shell interpolation"

    def test_passes_shell_vars_as_arguments(self):
        """Shell variables should be passed as arguments after the Python code."""
        content = SCRIPT_PATH.read_text()

        # After the closing quote of the Python -c block, the shell variables
        # should appear as arguments
        assert '"${COUNT}" "${LABEL}"' in content or (
            '"$COUNT" "$LABEL"' in content
        ), "Shell variables should be passed as arguments to the Python command"
