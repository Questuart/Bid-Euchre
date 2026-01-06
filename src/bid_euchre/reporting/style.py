"""
Shared visual styling for all Bid Euchre reports.

Ensures consistency across dashboards, paired comparisons, and head-to-head reports.
"""


import matplotlib.pyplot as plt

# ================================
# Contract Styling
# ================================

CONTRACT_LABELS = {
    "suit_C": "Trump-C",
    "suit_D": "Trump-D",
    "suit_H": "Trump-H",
    "suit_S": "Trump-S",
    "high": "NT:High",
    "low": "NT:Low",
}

CONTRACT_COLORS = {
    "suit_C": "#3498db",  # Blue (Clubs)
    "suit_D": "#e67e22",  # Orange (Diamonds)
    "suit_H": "#9b59b6",  # Purple (Hearts)
    "suit_S": "#34495e",  # Dark gray (Spades)
    "high": "#27ae60",    # Green (High)
    "low": "#e74c3c",     # Red (Low)
}


# ================================
# Strategy Styling
# ================================

STRATEGY_NAMES = {
    "greedy": "Greedy",
    "improved_greedy": "Improved Greedy",
    "random_legal": "Random Legal",
    "always_lowest": "Always Lowest",
    "always_highest": "Always Highest",
    "basic": "Basic",
}

STRATEGY_COLORS = {
    "greedy": "#2ecc71",
    "improved_greedy": "#27ae60",
    "random_legal": "#95a5a6",
    "always_lowest": "#3498db",
    "always_highest": "#e74c3c",
    "basic": "#f39c12",
}


# ================================
# Typography & Layout
# ================================

REPORT_STYLE = {
    # Font sizes
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8,
    "figure.titlesize": 14,
    
    # Line widths
    "lines.linewidth": 1.5,
    "axes.linewidth": 1.0,
    "grid.linewidth": 0.5,
    
    # Colors
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "axes.edgecolor": "#333",
    "grid.color": "#ccc",
    "grid.alpha": 0.3,
    
    # Grid
    "axes.grid": False,  # Enable per-plot
    "grid.linestyle": "--",
}


# ================================
# Outcome Styling (Win/Push/Loss)
# ================================

OUTCOME_COLORS = {
    "win": "#27ae60",   # Green
    "push": "#f39c12",  # Orange/Yellow
    "loss": "#e74c3c",  # Red
}

OUTCOME_LABELS = {
    "win": "Win (≥6 tricks)",
    "push": "Push (5 tricks)",
    "loss": "Loss (≤4 tricks)",
}


# ================================
# Standard Figure Sizes
# ================================

FIGSIZE_DASHBOARD = (14, 12)  # Main 3×3 dashboard
FIGSIZE_SINGLE_PLOT = (8, 6)  # Individual analysis plot
FIGSIZE_COMPARISON = (18, 12)  # Multi-strategy comparison
FIGSIZE_MATRIX = (10, 8)      # Heatmap/matrix


# ================================
# Helper Functions
# ================================

def apply_report_style():
    """Apply standard report styling to matplotlib."""
    plt.rcParams.update(REPORT_STYLE)


def format_pct(value: float, decimals: int = 1) -> str:
    """Format a proportion as percentage string."""
    return f"{value * 100:.{decimals}f}%"


def format_ci(lower: float, upper: float, decimals: int = 1, as_pct: bool = True) -> str:
    """Format a confidence interval as a string."""
    if as_pct:
        return f"[{lower * 100:.{decimals}f}%, {upper * 100:.{decimals}f}%]"
    else:
        return f"[{lower:.{decimals}f}, {upper:.{decimals}f}]"


def get_contract_label(contract_type: str, trump_suit: str = None) -> str:
    """Get display label for a contract."""
    if contract_type == "suit" and trump_suit:
        key = f"suit_{trump_suit}"
    else:
        key = contract_type
    return CONTRACT_LABELS.get(key, key)


def get_contract_color(contract_type: str, trump_suit: str = None) -> str:
    """Get color for a contract."""
    if contract_type == "suit" and trump_suit:
        key = f"suit_{trump_suit}"
    else:
        key = contract_type
    return CONTRACT_COLORS.get(key, "#95a5a6")


def get_strategy_name(strategy_id: str) -> str:
    """Get display name for a strategy."""
    return STRATEGY_NAMES.get(strategy_id, strategy_id)


def get_strategy_color(strategy_id: str) -> str:
    """Get color for a strategy."""
    return STRATEGY_COLORS.get(strategy_id, "#95a5a6")

