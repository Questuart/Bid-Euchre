"""Hypothesis settings for property-based tests.

These settings balance thoroughness with CI speed.
"""

from hypothesis import Verbosity, settings

# Default CI profile: fast enough for regular CI runs
settings.register_profile(
    "ci",
    max_examples=50,
    deadline=None,  # Disable deadline for simulation tests
    verbosity=Verbosity.normal,
)

# Thorough profile for pre-release validation
settings.register_profile(
    "thorough",
    max_examples=500,
    deadline=None,
    verbosity=Verbosity.verbose,
)

# Debug profile for investigating failures
settings.register_profile(
    "debug",
    max_examples=10,
    deadline=None,
    verbosity=Verbosity.verbose,
)

# Load CI profile by default
settings.load_profile("ci")
