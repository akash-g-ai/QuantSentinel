"""Tests for audit in quantsentinel.audit."""

from pathlib import Path

import pytest

from quantsentinel.models import Finding, StageResult, ValidationReport, ValidationStatus
from quantsentinel.quality import AssessedReport, QualityAssessment, StatusCounts
from quantsentinel.audit import AuditDatabase, RunRecord, RunSummary, StageRecord, FindingRecord


class TestAuditDatabase:
    """Tests for AuditDatabase class."""

    def _make_assessed_report(self) -> AssessedReport:
        """Create a sample AssessedReport for testing."""
        report = ValidationReport(
            dataset_name="audit_test.csv",
            stage_results=[
                StageResult(
                    stage_name="structural",
                    findings=[
                        Finding(rule_id="REQUIRED_COLUMNS", status=ValidationStatus.PASS, message="OK"),
                        Finding(rule_id="MISSING_VALUES", status=ValidationStatus.FAIL, message="Found", affected_rows=(1,)),
                    ],
                ),
            ],
        )
        assessment = QualityAssessment(
            overall_status=ValidationStatus.FAIL,
            score=87,
            total_penalty=13,
            status_counts=StatusCounts(pass_count=1, warning_count=0, fail_count=1),
            summary="Test audit record",
        )
        return AssessedReport(report=report, assessment=assessment)

    def test_create_and_record(self, tmp_path: Path) -> None:
        """Create database and record a run."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            assessed = self._make_assessed_report()
            run_id = db.record_run(assessed)

            assert isinstance(run_id, str)
            assert len(run_id) == 36  # UUID4 format

        assert db_path.exists()

    def test_list_runs(self, tmp_path: Path) -> None:
        """list_runs should return run summaries."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            assessed = self._make_assessed_report()
            db.record_run(assessed)

            runs = db.list_runs()

            assert len(runs) == 1
            assert isinstance(runs[0], RunSummary)
            assert runs[0].dataset_name == "audit_test.csv"
            assert runs[0].overall_status == "FAIL"

    def test_list_runs_by_dataset(self, tmp_path: Path) -> None:
        """list_runs with dataset filter should work."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            assessed = self._make_assessed_report()
            db.record_run(assessed)

            # Create another dataset
            report2 = ValidationReport(
                dataset_name="other.csv",
                stage_results=[StageResult(stage_name="structural", findings=[])],
            )
            assessment2 = QualityAssessment(
                overall_status=ValidationStatus.PASS,
                score=100,
                total_penalty=0,
                status_counts=StatusCounts(pass_count=0, warning_count=0, fail_count=0),
                summary="Other",
            )
            db.record_run(AssessedReport(report=report2, assessment=assessment2))

            # Filter
            runs = db.list_runs(dataset_name="audit_test.csv")

            assert len(runs) == 1
            assert runs[0].dataset_name == "audit_test.csv"

    def test_get_run(self, tmp_path: Path) -> None:
        """get_run should return a RunRecord or None."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            assessed = self._make_assessed_report()
            run_id = db.record_run(assessed)

            run = db.get_run(run_id)

            assert run is not None
            assert isinstance(run, RunRecord)
            assert run.dataset_name == "audit_test.csv"
            assert run.overall_status == "FAIL"
            assert run.quality_score == 87

    def test_get_run_missing(self, tmp_path: Path) -> None:
        """get_run for non-existent run should return None."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            run = db.get_run("nonexistent-id")

            assert run is None

    def test_get_stage_results(self, tmp_path: Path) -> None:
        """get_stage_results should return stage records."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            assessed = self._make_assessed_report()
            run_id = db.record_run(assessed)

            stages = db.get_stage_results(run_id)

            assert len(stages) == 1
            assert stages[0].stage_name == "structural"
            assert stages[0].status == "FAIL"
            assert stages[0].finding_count == 2

    def test_get_findings(self, tmp_path: Path) -> None:
        """get_findings should return finding records."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            assessed = self._make_assessed_report()
            run_id = db.record_run(assessed)

            findings = db.get_findings(run_id)

            assert len(findings) == 2
            assert findings[0].rule_id == "REQUIRED_COLUMNS"
            assert findings[0].status == "PASS"
            assert findings[1].rule_id == "MISSING_VALUES"
            assert findings[1].status == "FAIL"
            assert findings[1].affected_row_count == 1
            assert findings[1].affected_rows == (1,)

    def test_context_manager(self, tmp_path: Path) -> None:
        """AuditDatabase should work as a context manager."""
        db_path = tmp_path / "audit.db"

        run_id = None
        with AuditDatabase(str(db_path)) as db:
            assessed = self._make_assessed_report()
            run_id = db.record_run(assessed)

        # After exiting, connection should be closed
        # Verify by re-opening the same db file
        with AuditDatabase(str(db_path)) as db2:
            run = db2.get_run(run_id)
            assert run is not None
            assert run.dataset_name == "audit_test.csv"

    def test_manual_close(self, tmp_path: Path) -> None:
        """AuditDatabase.close() should close the connection."""
        db_path = tmp_path / "audit.db"

        db = AuditDatabase(str(db_path))
        try:
            assessed = self._make_assessed_report()
            db.record_run(assessed)
            db.close()

            # Re-opening should succeed if connection was closed
            db2 = AuditDatabase(str(db_path))
            db2.close()
        finally:
            if hasattr(db, "_conn") and not getattr(db._conn, "closed", True):
                db.close()

    def test_parameterized_queries(self, tmp_path: Path) -> None:
        """Database operations should use parameterized queries (no SQL injection)."""
        db_path = tmp_path / "audit.db"

        # Malicious dataset name (SQL injection attempt)
        malicious_name = 'test"; DROP TABLE runs; --'

        with AuditDatabase(str(db_path)) as db:
            report = ValidationReport(
                dataset_name=malicious_name,
                stage_results=[StageResult(stage_name="structural", findings=[])],
            )
            assessment = QualityAssessment(
                overall_status=ValidationStatus.PASS,
                score=100,
                total_penalty=0,
                status_counts=StatusCounts(pass_count=0, warning_count=0, fail_count=0),
                summary="Test",
            )
            run_id = db.record_run(AssessedReport(report=report, assessment=assessment))

            # Verify the name was stored safely
            run = db.get_run(run_id)
            assert run is not None
            assert malicious_name in run.dataset_name

            # Verify the table still exists (check that stages were recorded)
            stages = db.get_stage_results(run_id)
            assert len(stages) == 1
            assert stages[0].stage_name == "structural"

    def test_empty_report(self, tmp_path: Path) -> None:
        """Recording an empty report should work."""
        db_path = tmp_path / "audit.db"

        with AuditDatabase(str(db_path)) as db:
            report = ValidationReport(
                dataset_name="empty.csv",
                stage_results=[],
            )
            assessment = QualityAssessment(
                overall_status=ValidationStatus.PASS,
                score=100,
                total_penalty=0,
                status_counts=StatusCounts(pass_count=0, warning_count=0, fail_count=0),
                summary="Empty report",
            )
            run_id = db.record_run(AssessedReport(report=report, assessment=assessment))

            run = db.get_run(run_id)
            assert run is not None
            assert run.total_findings == 0