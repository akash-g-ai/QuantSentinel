"""Tests for quality assessment in quantsentinel.quality."""

from pathlib import Path

import pytest

from quantsentinel.models import Finding, StageResult, ValidationReport, ValidationStatus
from quantsentinel.quality import assess_quality, AssessedReport, QualityAssessment, StatusCounts


class TestAssessQuality:
    """Tests for assess_quality() function."""

    def _make_stage(self, name: str, status: ValidationStatus) -> StageResult:
        return StageResult(
            stage_name=name,
            findings=[
                Finding(
                    rule_id="TEST",
                    status=status,
                    message="test",
                ),
            ],
        )

    def test_all_pass_returns_pass(self, tmp_path: Path) -> None:
        """A report with all PASS findings should have overall PASS."""
        report = ValidationReport(
            dataset_name="clean.csv",
            stage_results=[
                self._make_stage("structural", ValidationStatus.PASS),
                self._make_stage("financial", ValidationStatus.PASS),
                self._make_stage("statistical", ValidationStatus.PASS),
            ],
        )

        assessed = assess_quality(report)

        assert assessed.assessment.overall_status == ValidationStatus.PASS
        assert assessed.assessment.score == 100
        assert assessed.assessment.total_penalty == 0
        assert assessed.assessment.status_counts.pass_count == 3
        assert "passed all validation checks" in assessed.assessment.summary

    def test_one_fail_returns_fail(self, tmp_path: Path) -> None:
        """Any FAIL finding should result in overall FAIL."""
        report = ValidationReport(
            dataset_name="bad.csv",
            stage_results=[
                self._make_stage("structural", ValidationStatus.PASS),
                self._make_stage("financial", ValidationStatus.FAIL),
                self._make_stage("statistical", ValidationStatus.WARNING),
            ],
        )

        assessed = assess_quality(report)

        assert assessed.assessment.overall_status == ValidationStatus.FAIL
        assert assessed.assessment.score == 100 - 10 - 3  # 87
        assert assessed.assessment.status_counts.fail_count == 1
        assert "failed validation" in assessed.assessment.summary

    def test_only_warnings_returns_warning(self, tmp_path: Path) -> None:
        """No FAIL but any WARNING should result in overall WARNING."""
        report = ValidationReport(
            dataset_name="warned.csv",
            stage_results=[
                self._make_stage("structural", ValidationStatus.WARNING),
                self._make_stage("financial", ValidationStatus.WARNING),
            ],
        )

        assessed = assess_quality(report)

        assert assessed.assessment.overall_status == ValidationStatus.WARNING
        assert assessed.assessment.score == 100 - 3 - 3  # 94
        assert "passed with warnings" in assessed.assessment.summary

    def test_scoring_formula(self, tmp_path: Path) -> None:
        """Verify the scoring formula: score = max(0, 100 - (FAIL*10 + WARN*3))."""
        report = ValidationReport(
            dataset_name="mixed.csv",
            stage_results=[
                StageResult(
                    stage_name="structural",
                    findings=[
                        # 2 FAIL + 3 WARNING + 5 PASS = 20 + 9 = 29 penalty
                        *[Finding(rule_id=f"F{i}", status=ValidationStatus.FAIL, message="") for i in range(2)],
                        *[Finding(rule_id=f"W{i}", status=ValidationStatus.WARNING, message="") for i in range(3)],
                        *[Finding(rule_id=f"P{i}", status=ValidationStatus.PASS, message="") for i in range(5)],
                    ],
                ),
            ],
        )

        assessed = assess_quality(report)

        assert assessed.assessment.score == 100 - (2 * 10 + 3 * 3)  # 71
        assert assessed.assessment.total_penalty == 29

    def test_score_capped_at_zero(self, tmp_path: Path) -> None:
        """Score should never go below 0."""
        report = ValidationReport(
            dataset_name="bad.csv",
            stage_results=[
                StageResult(
                    stage_name="structural",
                    findings=[
                        Finding(rule_id="F", status=ValidationStatus.FAIL, message="")
                        for _ in range(20)  # 200 penalty, but score capped at 0
                    ],
                ),
            ],
        )

        assessed = assess_quality(report)

        assert assessed.assessment.score == 0
        assert assessed.assessment.overall_status == ValidationStatus.FAIL

    def test_report_preserved_unchanged(self, tmp_path: Path) -> None:
        """The original report should not be modified."""
        report = ValidationReport(
            dataset_name="clean.csv",
            stage_results=[
                self._make_stage("structural", ValidationStatus.PASS),
            ],
        )

        assessed = assess_quality(report)

        # Original report unchanged
        assert len(report.stage_results) == 1
        assert report.stage_results[0].finding_count == 1

        # AssessedReport holds the original by reference
        assert assessed.report is report

    def test_status_counts(self, tmp_path: Path) -> None:
        """StatusCounts should be accurate."""
        report = ValidationReport(
            dataset_name="mixed.csv",
            stage_results=[
                StageResult(
                    stage_name="structural",
                    findings=[
                        Finding(rule_id="P1", status=ValidationStatus.PASS, message=""),
                        Finding(rule_id="P2", status=ValidationStatus.PASS, message=""),
                        Finding(rule_id="W1", status=ValidationStatus.WARNING, message=""),
                        Finding(rule_id="F1", status=ValidationStatus.FAIL, message=""),
                    ],
                ),
            ],
        )

        assessed = assess_quality(report)

        counts = assessed.assessment.status_counts
        assert counts.pass_count == 2
        assert counts.warning_count == 1
        assert counts.fail_count == 1
        assert counts.total == 4

    def test_report_required(self, tmp_path: Path) -> None:
        """assess_quality should raise TypeError for non-ValidationReport."""
        with pytest.raises(TypeError, match="expects a ValidationReport"):
            assess_quality("not a report")  # type: ignore[arg-type]