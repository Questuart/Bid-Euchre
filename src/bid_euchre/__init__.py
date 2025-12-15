"""
Bid Euchre Simulation Framework

A comprehensive framework for simulating and analyzing the card game Bid Euchre
with various AI strategies and experimental configurations.
"""

try:
    from . import experiments
    HAS_EXPERIMENTS = True
    __all__ = ["experiments"]
except ImportError:
    HAS_EXPERIMENTS = False
    __all__ = []

__version__ = "0.1.0"
