import matplotlib.pyplot as plt
import pytest

from bid_euchre.reporting import style


def test_apply_report_style_updates_rcparams():
    style.apply_report_style()
    assert plt.rcParams["font.size"] == style.REPORT_STYLE["font.size"]
    assert plt.rcParams["axes.titlesize"] == style.REPORT_STYLE["axes.titlesize"]
    assert plt.rcParams["grid.linewidth"] == style.REPORT_STYLE["grid.linewidth"]


def test_plotly_template_matches_style():
    try:
        import plotly.io as pio
    except ImportError:
        pytest.skip("plotly not installed")

    template_name = style.apply_plotly_template()
    template = pio.templates[template_name]
    layout = template.layout

    assert layout.font.size == style.REPORT_STYLE["font.size"]
    assert layout.title.font.size == style.REPORT_STYLE["figure.titlesize"]
    assert list(layout.colorway) == style.BASE_COLORS
