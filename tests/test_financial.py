"""Tests for financial validation in quantsentinel.financial."""

from pathlib import Path

import pandas as pd
import pytest

from quantsentinel.models import ValidationStatus
from quantsentinel.financial import validate_financial


class TestValidateFinancial:
    """Tests for validate_financial() function."""

    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_clean_data_passes(self, tmp_path: Path) -> None:
        """A clean OHLCV dataset should pass all financial checks."""
        df = self._make_df([
            {"date": "2024-01-02", "open": 100, "high": 105, "low": 98, "close": 103, "volume": 1000},
            {"date": "2024-01-03", "open": 103, "high": 108, "low": 101, "close": 106, "volume": 1200},
        ])
        df = df.rename(columns=str.title)
        result = validate_financial(df)

        assert result.stage_name == "financial"
        assert result.status == ValidationStatus.PASS
        assert len(result.findings) == 5

    def test_ohlc_violation_fails(self, tmp_path: Path) -> None:
        """High < Low should fail OHLC_CONSISTENCY."""
        df = self._make_df([
            {"Date": "2024-01-02", "Open": 100, "High": 95, "Low": 98, "Close": 96, "Volume": 1000},
        ])
        result = validate_financial(df)

        ohlc = next(f for f in result.findings if f.rule_id == "OHLC_CONSISTENCY")
        assert ohlc.status == ValidationStatus.FAIL
        assert "High < Low" in ohlc.metadata["breakdown"]

    def test_non_positive_price_fails(self, tmp_path: Path) -> None:
        """Zero or negative prices should fail NON_POSITIVE_PRICES."""
        df = self._make_df([
            {"Date": "2024-01-02", "Open": 0, "High": 105, "Low": 98, "Close": 103, "Volume": 1000},
        ])
        result = validate_financial(df)

        prices = next(f for f in result.findings if f.rule_id == "NON_POSITIVE_PRICES")
        assert prices.status == ValidationStatus.FAIL
        assert "Open" in prices.metadata["columns_with_non_positive"]

    def test_negative_volume_fails(self, tmp_path: Path) -> None:
        """Negative volume should fail INVALID_VOLUME."""
        df = self._make_df([
            {"Date": "2024-01-02", "Open": 100, "High": 105, "Low": 98, "Close": 103, "Volume": -100},
        ])
        result = validate_financial(df)

        volume = next(f for f in result.findings if f.rule_id == "INVALID_VOLUME")
        assert volume.status == ValidationStatus.FAIL

    def test_zero_volume_warns(self, tmp_path: Path) -> None:
        """Zero volume should warn but not fail."""
        df = self._make_df([
            {"Date": "2024-01-02", "Open": 100, "High": 105, "Low": 98, "Close": 103, "Volume": 0},
        ])
        result = validate_financial(df)

        volume = next(f for f in result.findings if f.rule_id == "INVALID_VOLUME")
        assert volume.status == ValidationStatus.WARNING

    def test_invalid_date_fails(self, tmp_path: Path) -> None:
        """Unparseable date should fail TRADING_DATE_VALIDITY."""
        df = self._make_df([
            {"Date": "not-a-date", "Open": 100, "High": 105, "Low": 98, "Close": 103, "Volume": 1000},
        ])
        result = validate_financial(df)

        date = next(f for f in result.findings if f.rule_id == "TRADING_DATE_VALIDITY")
        assert date.status == ValidationStatus.FAIL

    def test_duplicate_dates_warn(self, tmp_path: Path) -> None:
        """Same date on multiple rows should warn."""
        df = self._make_df([
            {"Date": "2024-01-02", "Open": 100, "High": 105, "Low": 98, "Close": 103, "Volume": 1000},
            {"Date": "2024-01-02", "Open": 101, "High": 106, "Low": 99, "Close": 104, "Volume": 1100},
        ])
        result = validate_financial(df)

        dup = next(f for f in result.findings if f.rule_id == "DUPLICATE_DATES")
        assert dup.status == ValidationStatus.WARNING

    def test_dataframe_required(self) -> None:
        """validate_financial should raise TypeError for non-DataFrame."""
        with pytest.raises(TypeError, match="expects a pandas DataFrame"):
            validate_financial("not a dataframe")  # type: ignore[arg-type]