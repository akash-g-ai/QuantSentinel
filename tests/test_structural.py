"""Tests for structural validation in quantsentinel.structural."""

from pathlib import Path

import pandas as pd
import pytest

from quantsentinel.models import ValidationStatus
from quantsentinel.structural import validate_structure


class TestValidateStructure:
    """Tests for validate_structure() function."""

    def test_passing_dataframe_returns_pass_findings(self, tmp_path: Path) -> None:
        """A clean CSV with all required columns should pass all structural checks."""
        csv_path = tmp_path / "clean.csv"
        csv_path.write_text(
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,100,105,98,103,1000\n"
            "2024-01-03,103,108,101,106,1200\n",
            encoding="utf-8",
        )

        df = pd.read_csv(csv_path)
        result = validate_structure(df)

        assert result.stage_name == "structural"
        assert result.status == ValidationStatus.PASS
        assert len(result.findings) == 5

        # Required_COLUMNS must pass
        required = next(f for f in result.findings if f.rule_id == "REQUIRED_COLUMNS")
        assert required.status == ValidationStatus.PASS

    def test_missing_column_fails(self, tmp_path: Path) -> None:
        """Missing a required column should fail REQUIRED_COLUMNS."""
        csv_path = tmp_path / "missing.csv"
        csv_path.write_text(
            "Date,Open,High,Low,Close\n"
            "2024-01-02,100,105,98,103\n",
            encoding="utf-8",
        )  # Missing Volume

        df = pd.read_csv(csv_path)
        result = validate_structure(df)

        required = next(f for f in result.findings if f.rule_id == "REQUIRED_COLUMNS")
        assert required.status == ValidationStatus.FAIL
        assert "Volume" in required.metadata["missing_columns"]

        # Other checks should emit skip messages
        assert result.status == ValidationStatus.FAIL
        assert len(result.findings) == 5  # All rules produce a finding

    def test_missing_values_fail(self, tmp_path: Path) -> None:
        """Missing values in required columns should fail MISSING_VALUES."""
        csv_path = tmp_path / "missing_values.csv"
        csv_path.write_text(
            "date,open,high,low,close,volume\n"
            "2024-01-02,100,105,98,103,1000\n"
            "2024-01-03,103,,101,106,1200\n",  # Missing High
            encoding="utf-8",
        )

        df = pd.read_csv(csv_path)
        result = validate_structure(df)

        missing = next(f for f in result.findings if f.rule_id == "MISSING_VALUES")
        assert missing.status == ValidationStatus.FAIL
        assert "High" in missing.metadata["columns_with_nulls"]

    def test_duplicate_records_warn(self, tmp_path: Path) -> None:
        """Duplicate rows should trigger DUPLICATE_RECORDS as WARNING."""
        csv_path = tmp_path / "duplicates.csv"
        csv_path.write_text(
            "date,open,high,low,close,volume\n"
            "2024-01-02,100,105,98,103,1000\n"
            "2024-01-03,103,108,101,106,1200\n"
            "2024-01-02,100,105,98,103,1000\n",  # Duplicate of first row
            encoding="utf-8",
        )

        df = pd.read_csv(csv_path)
        result = validate_structure(df)

        dup = next(f for f in result.findings if f.rule_id == "DUPLICATE_RECORDS")
        assert dup.status == ValidationStatus.WARNING
        assert len(dup.affected_rows) == 2  # Both duplicate rows are flagged

    def test_case_insensitive_column_matching(self, tmp_path: Path) -> None:
        """Column matching should be case-insensitive."""
        csv_path = tmp_path / "mixed_case.csv"
        csv_path.write_text(
            "DATE,OPEN,HIGH,LOW,CLOSE,VOLUME\n"
            "2024-01-02,100,105,98,103,1000\n"
            "2024-01-03,103,108,101,106,1200\n",
            encoding="utf-8",
        )

        df = pd.read_csv(csv_path)
        result = validate_structure(df)

        required = next(f for f in result.findings if f.rule_id == "REQUIRED_COLUMNS")
        assert required.status == ValidationStatus.PASS

    def test_data_type_check_fails_on_invalid(self, tmp_path: Path) -> None:
        """Invalid data types should be detected."""
        csv_path = tmp_path / "bad_types.csv"
        csv_path.write_text(
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,100,105,98,103,1000\n"
            "2024-01-03,not_a_number,108,101,106,1200\n",  # Invalid Open
            encoding="utf-8",
        )

        df = pd.read_csv(csv_path)
        result = validate_structure(df)

        dtype_check = next(f for f in result.findings if f.rule_id == "DATA_TYPES")
        assert dtype_check.status == ValidationStatus.FAIL
        assert "Open" in dtype_check.metadata["type_failures"][0]

    def test_dataframe_required(self) -> None:
        """validate_structure should raise TypeError for non-DataFrame."""
        with pytest.raises(TypeError, match="expects a pandas DataFrame"):
            validate_structure("not a dataframe")  # type: ignore[arg-type]

    def test_empty_dataframe_fails_required_columns(self) -> None:
        """Empty DataFrame should fail REQUIRED_COLUMNS."""
        df = pd.DataFrame()
        result = validate_structure(df)

        required = next(f for f in result.findings if f.rule_id == "REQUIRED_COLUMNS")
        assert required.status == ValidationStatus.FAIL
        assert len(required.metadata["missing_columns"]) == 6