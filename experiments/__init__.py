"""Experiments package initialization.

This module ensures all experiment scripts can import from src/
without manual sys.path manipulation.

Usage:
    Simply place your experiment script in the experiments/ directory
    and imports will work automatically:

    # No need for sys.path.insert(0, 'src')!
    from bid_euchre.sim import simulation
    from bid_euchre.strategy import GreedyStrategy
"""
import sys
import os

_experiments_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_experiments_dir)
_src_path = os.path.join(_project_root, 'src')

if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
