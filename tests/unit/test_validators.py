"""Unit tests for diagnostics validators."""

import pandas as pd

from bid_euchre.diagnostics.validators import (
    SampleSizeValidator,
    SampleSizeWarning,
)


class TestSampleSizeValidator:
    """Tests for SampleSizeValidator."""

    def test_validate_returns_none_for_sufficient_size(self):
        """Sufficient sample size should return None."""
        warning = SampleSizeValidator.validate(3000, "bias_detection")
        assert warning is None

    def test_validate_returns_warning_for_insufficient_size(self):
        """Insufficient sample size should return SampleSizeWarning."""
        warning = SampleSizeValidator.validate(500, "bias_detection")
        assert warning is not None
        assert isinstance(warning, SampleSizeWarning)
        assert warning.purpose == "bias_detection"
        assert warning.actual == 500
        assert warning.minimum == 2000

    def test_validate_all_purposes(self):
        """Test validation for all purpose types."""
        # All should pass with large sample
        for purpose in ["bias_detection", "feature_correlation", "tail_analysis", "production", "smoke_test"]:
            warning = SampleSizeValidator.validate(100000, purpose)  # type: ignore
            assert warning is None, f"Should pass for {purpose} with n=100000"

        # All should warn with small sample (except smoke_test)
        for purpose in ["bias_detection", "feature_correlation", "tail_analysis", "production"]:
            warning = SampleSizeValidator.validate(50, purpose)  # type: ignore
            assert warning is not None, f"Should warn for {purpose} with n=50"

        # Smoke test should pass with small sample
        warning = SampleSizeValidator.validate(50, "smoke_test")
        assert warning is not None, "Should warn for smoke_test with n=50 (below 100)"

        warning = SampleSizeValidator.validate(150, "smoke_test")
        assert warning is None, "Should pass for smoke_test with n=150"

    def test_check_dataframe(self):
        """Test check_dataframe convenience method."""
        # Create test dataframes
        df_large = pd.DataFrame({"x": range(60000)})  # Above production minimum
        df_small = pd.DataFrame({"x": range(100)})

        # Large dataframe should pass all checks
        assert SampleSizeValidator.check_dataframe(df_large, "production") is None

        # Small dataframe should warn for production
        warning = SampleSizeValidator.check_dataframe(df_small, "production")
        assert warning is not None
        assert warning.actual == 100
        assert warning.minimum == 50000

    def test_exact_threshold(self):
        """Test behavior at exact threshold boundaries."""
        # Exactly at threshold should pass
        warning = SampleSizeValidator.validate(2000, "bias_detection")
        assert warning is None

        # One below threshold should warn
        warning = SampleSizeValidator.validate(1999, "bias_detection")
        assert warning is not None


class TestSampleSizeWarning:
    """Tests for SampleSizeWarning dataclass."""

    def test_str_format(self):
        """Verify warning message format."""
        warning = SampleSizeWarning(
            purpose="bias_detection",
            actual=500,
            minimum=2000
        )
        message = str(warning)
        assert "⚠️" in message
        assert "bias_detection" in message
        assert "500" in message
        assert "2000" in message
        assert "<" in message  # Should show comparison

    def test_fields(self):
        """Verify dataclass fields."""
        warning = SampleSizeWarning(
            purpose="production",
            actual=1000,
            minimum=50000
        )
        assert warning.purpose == "production"
        assert warning.actual == 1000
        assert warning.minimum == 50000
