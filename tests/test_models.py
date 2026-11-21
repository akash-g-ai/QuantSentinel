"""Tests for shared validation models in quantsentinel.models."""

import pytest

from quantsentinel.models import (
    Finding,
    StageResult,
    ValidationReport,
    ValidationStatus,
)


# ===========================================================================
# ValidationStatus
# ===========================================================================

class TestValidationStatus:
    def test_members_exist(self) -> None:
        assert ValidationStatus.PASS
        assert ValidationStatus.WARNING
        assert ValidationStatus.FAIL

    def test_severity_order(self) -> None:
        assert ValidationStatus.PASS < ValidationStatus.WARNING
        assert ValidationStatus.WARNING < ValidationStatus.FAIL
        assert ValidationStatus.PASS < ValidationStatus.FAIL

    def test_equality(self) -> None:
        assert ValidationStatus.PASS == ValidationStatus.PASS
        assert ValidationStatus.FAIL != ValidationStatus.WARNING

    def test_max_returns_worst(self) -> None:
        statuses = [ValidationStatus.PASS, ValidationStatus.FAIL, ValidationStatus.WARNING]
        assert max(statuses) == ValidationStatus.FAIL

    def test_max_all_pass(self) -> None:
        assert max([ValidationStatus.PASS, ValidationStatus.PASS]) == ValidationStatus.PASS

    def test_comparison_with_non_status_raises(self) -> None:
        result = ValidationStatus.PASS.__lt__("PASS")
        assert result is NotImplemented


# ===========================================================================
# Finding
# ===========================================================================

class TestFinding:
    def test_minimal_pass_finding(self) -> None:
        f = Finding(
            rule_id="MISSING_VALUES",
            status=ValidationStatus.PASS,
            message="No missing values detected.",
        )
        assert f.rule_id == "MISSING_VALUES"
        assert f.status == ValidationStatus.PASS
        assert f.message == "No missing values detected."
        assert f.affected_rows == ()
        assert f.metadata == {}

    def test_fail_finding_with_affected_rows(self) -> None:
        f = Finding(
            rule_id="OHLC_CONSISTENCY",
            status=ValidationStatus.FAIL,
            message="High < Low on 2 rows.",
            affected_rows=(3, 7),
        )
        assert f.affected_rows == (3, 7)
        assert f.status == ValidationStatus.FAIL

    def test_warning_finding_with_metadata(self) -> None:
        f = Finding(
            rule_id="VOLUME_SPIKE",
            status=ValidationStatus.WARNING,
            message="Volume exceeds 5-sigma threshold.",
            affected_rows=(12,),
            metadata={"z_score": 6.1, "threshold": 5.0},
        )
        assert f.metadata["z_score"] == 6.1

    def test_finding_is_immutable(self) -> None:
        f = Finding(
            rule_id="DUPLICATE_ROWS",
            status=ValidationStatus.FAIL,
            message="Duplicate rows found.",
        )
        with pytest.raises((AttributeError, TypeError)):
            f.rule_id = "OTHER"  # type: ignore[misc]

    def test_empty_rule_id_raises(self) -> None:
        with pytest.raises(ValueError, match="rule_id must be a non-empty string"):
            Finding(rule_id="", status=ValidationStatus.PASS, message="ok")

    def test_whitespace_rule_id_raises(self) -> None:
        with pytest.raises(ValueError, match="rule_id must be a non-empty string"):
            Finding(rule_id="   ", status=ValidationStatus.PASS, message="ok")

    def test_invalid_status_type_raises(self) -> None:
        with pytest.raises(TypeError, match="ValidationStatus member"):
            Finding(rule_id="X", status="PASS", message="ok")  # type: ignore[arg-type]

    def test_non_string_message_raises(self) -> None:
        with pytest.raises(TypeError, match="message must be a string"):
            Finding(rule_id="X", status=ValidationStatus.PASS, message=42)  # type: ignore[arg-type]

    def test_list_affected_rows_raises(self) -> None:
        with pytest.raises(TypeError, match="must be a tuple"):
            Finding(
                rule_id="X",
                status=ValidationStatus.PASS,
                message="ok",
                affected_rows=[1, 2],  # type: ignore[arg-type]
            )

    def test_non_int_in_affected_rows_raises(self) -> None:
        with pytest.raises(TypeError, match="every element of affected_rows must be an int"):
            Finding(
                rule_id="X",
                status=ValidationStatus.PASS,
                message="ok",
                affected_rows=("a", "b"),  # type: ignore[arg-type]
            )

    def test_non_dict_metadata_raises(self) -> None:
        with pytest.raises(TypeError, match="metadata must be a dict"):
            Finding(
                rule_id="X",
                status=ValidationStatus.PASS,
                message="ok",
                metadata="extra",  # type: ignore[arg-type]
            )


# ===========================================================================
# StageResult
# ===========================================================================

class TestStageResult:
    def _pass_finding(self, rule_id: str = "R1") -> Finding:
        return Finding(rule_id=rule_id, status=ValidationStatus.PASS, message="ok")

    def _fail_finding(self, rule_id: str = "R2") -> Finding:
        return Finding(
            rule_id=rule_id,
            status=ValidationStatus.FAIL,
            message="bad",
            affected_rows=(0,),
        )

    def _warn_finding(self, rule_id: str = "R3") -> Finding:
        return Finding(rule_id=rule_id, status=ValidationStatus.WARNING, message="suspicious")

    def test_empty_stage_is_pass(self) -> None:
        sr = StageResult(stage_name="structural")
        assert sr.status == ValidationStatus.PASS
        assert sr.finding_count == 0

    def test_status_reflects_worst_finding(self) -> None:
        sr = StageResult(
            stage_name="financial",
            findings=[self._pass_finding(), self._warn_finding(), self._fail_finding()],
        )
        assert sr.status == ValidationStatus.FAIL

    def test_status_warning_when_no_fail(self) -> None:
        sr = StageResult(
            stage_name="statistical",
            findings=[self._pass_finding(), self._warn_finding()],
        )
        assert sr.status == ValidationStatus.WARNING

    def test_finding_count(self) -> None:
        sr = StageResult(
            stage_name="structural",
            findings=[self._pass_finding(), self._fail_finding()],
        )
        assert sr.finding_count == 2

    def test_findings_by_status(self) -> None:
        sr = StageResult(
            stage_name="financial",
            findings=[
                self._pass_finding("R1"),
                self._fail_finding("R2"),
                self._fail_finding("R3"),
                self._warn_finding("R4"),
            ],
        )
        assert len(sr.findings_by_status(ValidationStatus.FAIL)) == 2
        assert len(sr.findings_by_status(ValidationStatus.PASS)) == 1
        assert len(sr.findings_by_status(ValidationStatus.WARNING)) == 1

    def test_empty_stage_name_raises(self) -> None:
        with pytest.raises(ValueError, match="stage_name must be a non-empty string"):
            StageResult(stage_name="")

    def test_whitespace_stage_name_raises(self) -> None:
        with pytest.raises(ValueError, match="stage_name must be a non-empty string"):
            StageResult(stage_name="  ")

    def test_findings_must_be_list(self) -> None:
        with pytest.raises(TypeError, match="findings must be a list"):
            StageResult(stage_name="structural", findings=(self._pass_finding(),))  # type: ignore[arg-type]

    def test_stage_result_is_mutable(self) -> None:
        sr = StageResult(stage_name="structural")
        sr.findings.append(self._fail_finding())
        assert sr.status == ValidationStatus.FAIL


# ===========================================================================
# ValidationReport
# ===========================================================================

class TestValidationReport:
    def _stage(self, name: str, status: ValidationStatus) -> StageResult:
        msg = "ok" if status == ValidationStatus.PASS else "issue"
        return StageResult(
            stage_name=name,
            findings=[Finding(rule_id="R", status=status, message=msg)],
        )

    def test_empty_report_is_pass(self) -> None:
        report = ValidationReport(dataset_name="test.csv")
        assert report.status == ValidationStatus.PASS
        assert report.total_findings == 0

    def test_status_is_worst_across_stages(self) -> None:
        report = ValidationReport(
            dataset_name="prices.csv",
            stage_results=[
                self._stage("structural", ValidationStatus.PASS),
                self._stage("financial", ValidationStatus.WARNING),
                self._stage("statistical", ValidationStatus.FAIL),
            ],
        )
        assert report.status == ValidationStatus.FAIL

    def test_total_findings_sums_all_stages(self) -> None:
        sr1 = StageResult(
            stage_name="structural",
            findings=[
                Finding(rule_id="A", status=ValidationStatus.PASS, message="ok"),
                Finding(rule_id="B", status=ValidationStatus.FAIL, message="bad", affected_rows=(1,)),
            ],
        )
        sr2 = StageResult(
            stage_name="financial",
            findings=[
                Finding(rule_id="C", status=ValidationStatus.WARNING, message="warn"),
            ],
        )
        report = ValidationReport(dataset_name="data.csv", stage_results=[sr1, sr2])
        assert report.total_findings == 3

    def test_get_stage_returns_correct_result(self) -> None:
        sr = self._stage("structural", ValidationStatus.PASS)
        report = ValidationReport(dataset_name="data.csv", stage_results=[sr])
        assert report.get_stage("structural") is sr

    def test_get_stage_returns_none_for_missing(self) -> None:
        report = ValidationReport(dataset_name="data.csv")
        assert report.get_stage("nonexistent") is None

    def test_empty_dataset_name_raises(self) -> None:
        with pytest.raises(ValueError, match="dataset_name must be a non-empty string"):
            ValidationReport(dataset_name="")

    def test_whitespace_dataset_name_raises(self) -> None:
        with pytest.raises(ValueError, match="dataset_name must be a non-empty string"):
            ValidationReport(dataset_name="  ")

    def test_stage_results_must_be_list(self) -> None:
        with pytest.raises(TypeError, match="stage_results must be a list"):
            ValidationReport(dataset_name="d.csv", stage_results="bad")  # type: ignore[arg-type]

    def test_report_all_pass_stages(self) -> None:
        report = ValidationReport(
            dataset_name="clean.csv",
            stage_results=[
                self._stage("structural", ValidationStatus.PASS),
                self._stage("financial", ValidationStatus.PASS),
            ],
        )
        assert report.status == ValidationStatus.PASS
