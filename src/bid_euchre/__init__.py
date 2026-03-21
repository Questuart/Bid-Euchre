"""
Bid Euchre Simulation Framework

A comprehensive framework for simulating and analyzing the card game Bid Euchre
with various AI strategies and experimental configurations.
"""

__version__ = "0.1.0"


def __getattr__(name: str):
    """Lazy subpackage import — avoids eager strategy/ML imports on package load.

    ``bid_euchre.experiments`` transitively imports the full strategy tree
    (all bidder implementations, ML models, config parsing, etc.).  Deferring
    this import means that lightweight consumers such as ``bid_euchre.ops.*``
    and ``scripts/internal/ops.py`` do not pay the startup cost.

    The lazy import is transparent: ``from bid_euchre import experiments`` and
    ``import bid_euchre; bid_euchre.experiments`` both work as before.
    """
    if name == "experiments":
        import importlib

        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
