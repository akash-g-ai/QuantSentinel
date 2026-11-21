"""Tests for statistical validation in quantsentinel.statistical."""

from pathlib import Path

import pandas as pd
import pytest

from quantsentinel.models import ValidationStatus
from quantsentinel.statistical import validate_statistics


class TestValidateStatistics:
    """Tests for validate_statistics() function."""

    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_clean_data_passes(self, tmp_path: Path) -> None:
        """A clean dataset with sufficient observations should pass."""
        # Need at least 20 + 1 = 21 rows for volume rolling window
        rows = [{"Date": f"2024-01-{2+i:02d}", "Close": 100 + i, "Volume": 1000} for i in range(25)]
        df = self._make_df(rows)
        result = validate_statistics(df)

        assert result.stage_name == "statistical"
        assert result.status == ValidationStatus.PASS
        assert len(result.findings) == 3

    def test_abnormal_return_warns(self, tmp_path: Path) -> None:
        """A 25% daily return should trigger ABNORMAL_RETURNS (threshold 20%)."""
        df = self._make_df([
            {"Date": "2024-01-02", "Close": 100, "Volume": 1000},
            {"Date": "2024-01-03", "Close": 125, "Volume": 1500},  # +25% return
        ])
        result = validate_statistics(df, return_threshold=0.20)

        abnormal = next(f for f in result.findings if f.rule_id == "ABNORMAL_RETURNS")
        assert abnormal.status == ValidationStatus.WARNING

    def test_volume_spike_warns(self, tmp_path: Path) -> None:
        """A volume spike should trigger VOLUME_SPIKE."""
        # Create enough rows for a 20-period rolling window
        rows = [{"Date": "2024-01-02", "Close": 100 + i, "Volume": 1000} for i in range(25)]
        rows.append({"Date": "2024-01-31", "Close": 125, "Volume": 10000})  # Spike
        df = self._make_df(rows)
        result = validate_statistics(df, volume_window=20, volume_z_threshold=2.0)

        spike = next(f for f in result.findings if f.rule_id == "VOLUME_SPIKE")
        assert spike.status == ValidationStatus.WARNING

    def test_return_outlier_warns(self, tmp_path: Path) -> None:
        """An extreme return should trigger RETURN_OUTLIERS."""
        # Create returns with one extreme outlier
        rows = [{"Date": "2024-01-02", "Close": 100, "Volume": 1000}]
        for i in range(1, 20):
            rows.append({"Date": f"2024-01-0{2+i}", "Close": 100 + i * 0.5, "Volume": 1000})
        rows.append({"Date": "2024-02-01", "Close": 200, "Volume": 1000})  # +100% return
        df = self._make_df(rows)
        result = validate_statistics(df, mad_z_threshold=2.0)

        outliers = next(f for f in result.findings if f.rule_id == "RETURN_OUTLIERS")
        assert outliers.status == ValidationStatus.WARNING

    def test_missing_close_column_warns(self, tmp_path: Path) -> None:
        """Missing Close column should warn about skipped checks."""
        df = self._make_df([
            {"Date": "2024-01-02", "Volume": 1000},
        ])
        result = validate_statistics(df)

        # All return-based checks should warn about missing Close
        abnormal = next(f for f in result.findings if f.rule_id == "ABNORMAL_RETURNS")
        assert abnormal.status == ValidationStatus.WARNING
        assert "Close" in abnormal.message

    def test_parameter_validation(self, tmp_path: Path) -> None:
        """Invalid parameter values should raise ValueError."""
        df = self._make_df([{"Date": "2024-01-02", "Close": 100, "Volume": 1000}])

        with pytest.raises(ValueError, match="return_threshold must be positive"):
            validate_statistics(df, return_threshold=-0.1)

        with pytest.raises(ValueError, match="volume_window must be >= 2"):
            validate_statistics(df, volume_window=1)

        with pytest.raises(ValueError, match="volume_z_threshold must be positive"):
            validate_statistics(df, volume_z_threshold=0)

    def test_dataframe_required(self) -> None:
        """validate_statistics should raise TypeError for non-DataFrame."""
        with pytest.raises(TypeError, match="expects a pandas DataFrame"):
            validate_statistics("not a dataframe")  # type: ignore[arg-type]