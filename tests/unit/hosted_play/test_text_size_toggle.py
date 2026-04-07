"""Tests for the text size toggle accessibility feature.

Validates:
- base.html contains the toggle button and FOUC-prevention script
- accessibility.css contains the large-mode rule
- game.js contains the toggle wiring
"""

from __future__ import annotations

import os
import re

import jinja2
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
TEMPLATES_DIR = os.path.join(WEB_DIR, "templates")
STATIC_DIR = os.path.join(WEB_DIR, "static")


@pytest.fixture()
def env():
    """Jinja2 environment loading from web/templates/."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )


@pytest.fixture()
def base_html(env):
    """Render base.html with minimal context."""
    tmpl = env.get_template("base.html")
    # Provide link_uuid so the nav renders too
    return tmpl.render(link_uuid="test-uuid")


@pytest.fixture()
def accessibility_css():
    """Read accessibility.css content."""
    path = os.path.join(STATIC_DIR, "css", "accessibility.css")
    with open(path) as f:
        return f.read()


@pytest.fixture()
def game_js():
    """Read game.js content."""
    path = os.path.join(STATIC_DIR, "game.js")
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# base.html — toggle button
# ---------------------------------------------------------------------------


class TestBaseHtmlToggleButton:
    def test_toggle_button_present(self, base_html):
        assert 'id="text-size-toggle"' in base_html

    def test_toggle_button_has_aria_label(self, base_html):
        assert 'aria-label="Toggle large text"' in base_html

    def test_toggle_button_is_type_button(self, base_html):
        """type=button prevents accidental form submission."""
        assert 'type="button"' in base_html

    def test_toggle_button_has_class(self, base_html):
        assert 'class="text-size-toggle"' in base_html


# ---------------------------------------------------------------------------
# base.html — FOUC prevention script
# ---------------------------------------------------------------------------


class TestBaseHtmlFoucPrevention:
    def test_fouc_script_present(self, base_html):
        """Inline script must apply data-text-size before first paint."""
        assert "localStorage.getItem('textSize')" in base_html

    def test_fouc_script_sets_data_attribute(self, base_html):
        assert "data-text-size" in base_html
        assert "'large'" in base_html

    def test_fouc_script_before_game_js(self, base_html):
        """The FOUC script must appear before game.js to run first."""
        fouc_pos = base_html.find("localStorage.getItem('textSize')")
        game_js_pos = base_html.find("game.js")
        assert fouc_pos < game_js_pos, "FOUC script must precede game.js"

    def test_fouc_defaults_to_large(self, base_html):
        """Large text is the default — FOUC script must apply large unless
        user explicitly opted out (#2521 item 1)."""
        # The script should check for 'default' opt-out, not 'large' opt-in
        assert (
            "!=='default'" in base_html
        ), "FOUC script should default to large text (check for opt-out, not opt-in)"


# ---------------------------------------------------------------------------
# accessibility.css — large mode rule
# ---------------------------------------------------------------------------


class TestAccessibilityCssLargeMode:
    def test_large_mode_rule_exists(self, accessibility_css):
        assert 'html[data-text-size="large"]' in accessibility_css

    def test_large_mode_sets_font_size(self, accessibility_css):
        # The rule should set font-size: 125% (or similar percentage)
        pattern = r'html\[data-text-size="large"\]\s*\{\s*font-size:\s*125%;'
        assert re.search(
            pattern, accessibility_css
        ), "Expected html[data-text-size='large'] { font-size: 125%; }"

    def test_toggle_button_styles_exist(self, accessibility_css):
        assert ".text-size-toggle" in accessibility_css

    def test_active_state_style_exists(self, accessibility_css):
        """When large mode is active, the toggle button should look different."""
        assert 'html[data-text-size="large"] .text-size-toggle' in accessibility_css

    def test_reduced_motion_covers_toggle(self, accessibility_css):
        """The toggle button transition must be suppressed in reduced-motion mode."""
        assert "prefers-reduced-motion" in accessibility_css
        # Find the reduced-motion block that covers .text-size-toggle
        rm_section = accessibility_css[
            accessibility_css.find("prefers-reduced-motion") :
        ]
        assert ".text-size-toggle" in rm_section


# ---------------------------------------------------------------------------
# game.js — toggle logic
# ---------------------------------------------------------------------------


class TestGameJsToggleLogic:
    def test_text_size_key_defined(self, game_js):
        assert "TEXT_SIZE_KEY" in game_js
        assert "'textSize'" in game_js

    def test_get_text_size_function(self, game_js):
        assert "function getTextSize()" in game_js

    def test_set_text_size_function(self, game_js):
        assert "function setTextSize(" in game_js

    def test_toggle_text_size_function(self, game_js):
        assert "function toggleTextSize()" in game_js

    def test_attach_toggle_handler(self, game_js):
        assert "function attachTextSizeToggle()" in game_js

    def test_toggle_wired_in_initialize(self, game_js):
        """attachTextSizeToggle must be called from initialize()."""
        # Find the initialize function body
        init_start = game_js.find("function initialize()")
        init_block = game_js[init_start : init_start + 500]
        assert "attachTextSizeToggle()" in init_block

    def test_localstorage_persistence(self, game_js):
        """Toggle should read/write localStorage."""
        assert "localStorage.getItem(TEXT_SIZE_KEY)" in game_js
        assert "localStorage.setItem(TEXT_SIZE_KEY" in game_js

    def test_data_attribute_usage(self, game_js):
        """Toggle should set/remove data-text-size on documentElement."""
        assert "data-text-size" in game_js
        assert "document.documentElement" in game_js

    def test_large_is_default(self, game_js):
        """getTextSize should return 'large' when no preference is stored (#2521 item 1)."""
        # The function should treat missing/null localStorage as 'large'
        assert (
            "=== 'default' ? 'default' : 'large'" in game_js
        ), "getTextSize should default to 'large' when localStorage has no value"
