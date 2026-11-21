"""Tests for reporting in quantsentinel.reporting."""

import json

import pytest

from pathlib import Path

from quantsentinel.models import Finding, StageResult, ValidationReport, ValidationStatus
from quantsentinel.quality import AssessedReport, QualityAssessment, StatusCounts
from quantsentinel.reporting import build_text_summary, save_csv, save_json, save_text_summary, to_csv, to_json


class TestReporting:
    """Tests for reporting functions."""

    def _make_assessed_report(self) -> AssessedReport:
        """Create a sample AssessedReport for testing."""
        report = ValidationReport(
            dataset_name="test.csv",
            stage_results=[
                StageResult(
                    stage_name="structural",
                    findings=[
                        Finding(rule_id="R1", status=ValidationStatus.PASS, message="pass"),
                        Finding(rule_id="R2", status=ValidationStatus.FAIL, message="fail", affected_rows=(1, 2)),
                    ],
                ),
                StageResult(
                    stage_name="financial",
                    findings=[
                        Finding(rule_id="R3", status=ValidationStatus.WARNING, message="warn"),
                    ],
                ),
            ],
        )
        assessment = QualityAssessment(
            overall_status=ValidationStatus.FAIL,
            score=77,  # 100 - 10 (1 FAIL) - 3 (1 WARNING) = 87, but let's use 77 for variety
            total_penalty=23,
            status_counts=StatusCounts(pass_count=1, warning_count=1, fail_count=1),
            summary="Test summary",
        )
        return AssessedReport(report=report, assessment=assessment)

    def test_build_text_summary(self, tmp_path: Path) -> None:
        """build_text_summary should return a non-empty string."""
        assessed = self._make_assessed_report()
        text = build_text_summary(assessed)

        assert isinstance(text, str)
        assert len(text) > 0
        assert "test.csv" in text
        assert "FAIL" in text
        assert "Warning" in text or "WARNING" in text

    def test_to_json(self, tmp_path: Path) -> None:
        """to_json should produce valid JSON."""
        assessed = self._make_assessed_report()
        json_str = to_json(assessed)

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["dataset_name"] == "test.csv"
        assert data["overall_status"] == "FAIL"
        assert data["quality_score"] == 77

    def test_to_csv(self, tmp_path: Path) -> None:
        """to_csv should produce valid CSV with headers."""
        assessed = self._make_assessed_report()
        csv_str = to_csv(assessed)

        lines = csv_str.strip().split("\n")
        assert len(lines) >= 3  # header + at least 2 findings
        assert "stage" in lines[0]
        assert "rule_id" in lines[0]
        assert "status" in lines[0]

    def test_save_text_summary(self, tmp_path: Path) -> None:
        """save_text_summary should write file."""
        assessed = self._make_assessed_report()
        out_path = tmp_path / "summary.txt"

        result = save_text_summary(assessed, str(out_path))

        assert result == out_path
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "test.csv" in content

    def test_save_json(self, tmp_path: Path) -> None:
        """save_json should write file."""
        assessed = self._make_assessed_report()
        out_path = tmp_path / "report.json"

        result = save_json(assessed, str(out_path))

        assert result == out_path
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["dataset_name"] == "test.csv"

    def test_save_csv(self, tmp_path: Path) -> None:
        """save_csv should write file."""
        assessed = self._make_assessed_report()
        out_path = tmp_path / "findings.csv"

        result = save_csv(assessed, str(out_path))

        assert result == out_path
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "stage" in content

    def test_assessed_report_required(self, tmp_path: Path) -> None:
        """Reporting functions should raise TypeError for non-AssessedReport."""
        with pytest.raises(TypeError, match="Expected an AssessedReport"):
            build_text_summary("not assessed")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="Expected an AssessedReport"):
            to_json("not assessed")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="Expected an AssessedReport"):
            to_csv("not assessed")  # type: ignore[arg-type]

    def test_parent_directory_required(self, tmp_path: Path) -> None:
        """Save functions should raise FileNotFoundError for missing parent."""
        assessed = self._make_assessed_report()
        bad_path = tmp_path / "nonexistent" / "file.json"

        with pytest.raises(FileNotFoundError):
            save_json(assessed, str(bad_path))

    def test_report_data_integrity(self, tmp_path: Path) -> None:
        """The original report should not be modified during reporting."""
        assessed = self._make_assessed_report()
        original_count = assessed.report.total_findings

        _ = build_text_summary(assessed)
        _ = to_json(assessed)
        _ = to_csv(assessed)

        assert assessed.report.total_findings == original_count