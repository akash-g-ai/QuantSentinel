
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantsentinel.quality import AssessedReport


# ---------------------------------------------------------------------------
# DDL — table and index definitions
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT    NOT NULL,
    dataset_name    TEXT    NOT NULL,
    recorded_at     TEXT    NOT NULL,
    overall_status  TEXT    NOT NULL,
    quality_score   INTEGER NOT NULL,
    total_findings  INTEGER NOT NULL,
    pass_count      INTEGER NOT NULL,
    warning_count   INTEGER NOT NULL,
    fail_count      INTEGER NOT NULL,
    summary         TEXT    NOT NULL,
    PRIMARY KEY (run_id)
);

CREATE TABLE IF NOT EXISTS stage_results (
    id              INTEGER NOT NULL,
    run_id          TEXT    NOT NULL,
    stage_name      TEXT    NOT NULL,
    status          TEXT    NOT NULL,
    finding_count   INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
);

CREATE TABLE IF NOT EXISTS findings (
    id                  INTEGER NOT NULL,
    run_id              TEXT    NOT NULL,
    stage_name          TEXT    NOT NULL,
    rule_id             TEXT    NOT NULL,
    status              TEXT    NOT NULL,
    message             TEXT    NOT NULL,
    affected_row_count  INTEGER NOT NULL,
    affected_rows       TEXT    NOT NULL,
    metadata_json       TEXT    NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (run_id) REFERENCES runs (run_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_dataset
    ON runs (dataset_name);

CREATE INDEX IF NOT EXISTS idx_stage_results_run
    ON stage_results (run_id);

CREATE INDEX IF NOT EXISTS idx_findings_run
    ON findings (run_id);

CREATE INDEX IF NOT EXISTS idx_findings_rule
    ON findings (rule_id);
"""


# ---------------------------------------------------------------------------
# Read-result types  (plain dataclasses — no pandas)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunSummary:
    """Lightweight summary of one audit run, returned by list_runs()."""

    run_id: str
    dataset_name: str
    recorded_at: str
    overall_status: str
    quality_score: int
    total_findings: int
    pass_count: int
    warning_count: int
    fail_count: int


@dataclass(frozen=True)
class RunRecord:
    """Full audit record for one run, returned by get_run()."""

    run_id: str
    dataset_name: str
    recorded_at: str
    overall_status: str
    quality_score: int
    total_findings: int
    pass_count: int
    warning_count: int
    fail_count: int
    summary: str


@dataclass(frozen=True)
class StageRecord:
    """Audit record for one stage within a run."""

    run_id: str
    stage_name: str
    status: str
    finding_count: int


@dataclass(frozen=True)
class FindingRecord:
    """Audit record for one finding within a run."""

    run_id: str
    stage_name: str
    rule_id: str
    status: str
    message: str
    affected_row_count: int
    affected_rows: tuple[int, ...]
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# AuditDatabase
# ---------------------------------------------------------------------------

class AuditDatabase:
    """SQLite-backed audit log for QuantSentinel validation runs.

    Can be used as a context manager (preferred for short-lived operations)
    or held open for the lifetime of an application session.

    Usage as context manager::

        with AuditDatabase("audit.db") as db:
            run_id = db.record_run(assessed)
            history = db.list_runs()

    Usage without context manager::

        db = AuditDatabase("audit.db")
        run_id = db.record_run(assessed)
        db.close()

    Args:
        db_path: Path to the SQLite database file.  The file is created if
                 it does not exist.  The parent directory must already exist.

    Raises:
        TypeError:          db_path is not a string or Path.
        FileNotFoundError:  The parent directory of db_path does not exist.
        sqlite3.Error:      SQLite could not open or initialise the database.
    """

    def __init__(self, db_path: str | Path) -> None:
        if not isinstance(db_path, (str, Path)):
            raise TypeError(
                f"db_path must be a string or pathlib.Path, got {type(db_path)!r}"
            )
        resolved = Path(db_path)
        if not resolved.parent.exists():
            raise FileNotFoundError(
                f"Database parent directory does not exist: {resolved.parent}"
            )
        self._path = resolved
        self._conn: sqlite3.Connection = sqlite3.connect(str(resolved))
        self._conn.row_factory = sqlite3.Row
        self._initialise()

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "AuditDatabase":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _initialise(self) -> None:
        """Create tables and indexes if they do not exist."""
        try:
            self._conn.executescript(_DDL)
            self._conn.commit()
        except sqlite3.Error as exc:
            raise sqlite3.Error(
                f"Failed to initialise audit database at {self._path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Write — record a completed run
    # ------------------------------------------------------------------

    def record_run(self, assessed: AssessedReport) -> str:
        """Persist a completed validation run and return its run_id.

        All three tables (``runs``, ``stage_results``, ``findings``) are
        written inside a single transaction.  If anything fails, the entire
        transaction is rolled back and ``sqlite3.Error`` is raised.

        Args:
            assessed: The :class:`~quantsentinel.quality.AssessedReport`
                      returned by :func:`~quantsentinel.pipeline.run_pipeline`.

        Returns:
            The ``run_id`` string (a UUID4) assigned to this run.

        Raises:
            TypeError:       *assessed* is not an ``AssessedReport``.
            sqlite3.Error:   The write failed; the database is unchanged.
        """
        if not isinstance(assessed, AssessedReport):
            raise TypeError(
                f"record_run expects an AssessedReport, got {type(assessed)!r}"
            )

        run_id = str(uuid.uuid4())
        recorded_at = _utc_now()
        report = assessed.report
        qa = assessed.assessment
        counts = qa.status_counts

        try:
            with self._conn:  # transaction: auto-commit on success, rollback on error
                # --- runs row ---
                self._conn.execute(
                    """
                    INSERT INTO runs (
                        run_id, dataset_name, recorded_at,
                        overall_status, quality_score, total_findings,
                        pass_count, warning_count, fail_count, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        report.dataset_name,
                        recorded_at,
                        qa.overall_status.name,
                        qa.score,
                        counts.total,
                        counts.pass_count,
                        counts.warning_count,
                        counts.fail_count,
                        qa.summary,
                    ),
                )

                # --- stage_results rows ---
                for stage in report.stage_results:
                    self._conn.execute(
                        """
                        INSERT INTO stage_results (run_id, stage_name, status, finding_count)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            stage.stage_name,
                            stage.status.name,
                            stage.finding_count,
                        ),
                    )

                # --- findings rows ---
                for stage in report.stage_results:
                    for finding in stage.findings:
                        affected_rows_str = " ".join(
                            str(r) for r in finding.affected_rows
                        )
                        try:
                            metadata_json = json.dumps(
                                finding.metadata, ensure_ascii=False
                            )
                        except (TypeError, ValueError):
                            metadata_json = "{}"

                        self._conn.execute(
                            """
                            INSERT INTO findings (
                                run_id, stage_name, rule_id, status,
                                message, affected_row_count,
                                affected_rows, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                run_id,
                                stage.stage_name,
                                finding.rule_id,
                                finding.status.name,
                                finding.message,
                                len(finding.affected_rows),
                                affected_rows_str,
                                metadata_json,
                            ),
                        )

        except sqlite3.Error as exc:
            raise sqlite3.Error(
                f"Failed to record run for dataset '{report.dataset_name}': {exc}"
            ) from exc

        return run_id

    # ------------------------------------------------------------------
    # Read — single run
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> RunRecord | None:
        """Return the :class:`RunRecord` for *run_id*, or ``None`` if absent.

        Args:
            run_id: The UUID string returned by :meth:`record_run`.

        Raises:
            sqlite3.Error: The query failed.
        """
        try:
            row = self._conn.execute(
                """
                SELECT run_id, dataset_name, recorded_at, overall_status,
                       quality_score, total_findings,
                       pass_count, warning_count, fail_count, summary
                FROM   runs
                WHERE  run_id = ?
                """,
                (run_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise sqlite3.Error(f"get_run failed for run_id={run_id!r}: {exc}") from exc

        if row is None:
            return None
        return _row_to_run_record(row)

    # ------------------------------------------------------------------
    # Read — list runs
    # ------------------------------------------------------------------

    def list_runs(
        self,
        dataset_name: str | None = None,
    ) -> list[RunSummary]:
        """Return run summaries in descending recorded_at order.

        Args:
            dataset_name: When provided, only runs for this exact dataset
                          name are returned.  When ``None``, all runs are
                          returned.

        Returns:
            A list of :class:`RunSummary` objects, newest first.

        Raises:
            sqlite3.Error: The query failed.
        """
        try:
            if dataset_name is None:
                rows = self._conn.execute(
                    """
                    SELECT run_id, dataset_name, recorded_at, overall_status,
                           quality_score, total_findings,
                           pass_count, warning_count, fail_count
                    FROM   runs
                    ORDER BY recorded_at DESC
                    """,
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT run_id, dataset_name, recorded_at, overall_status,
                           quality_score, total_findings,
                           pass_count, warning_count, fail_count
                    FROM   runs
                    WHERE  dataset_name = ?
                    ORDER BY recorded_at DESC
                    """,
                    (dataset_name,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise sqlite3.Error(f"list_runs failed: {exc}") from exc

        return [_row_to_run_summary(row) for row in rows]

    # ------------------------------------------------------------------
    # Read — stage results for a run
    # ------------------------------------------------------------------

    def get_stage_results(self, run_id: str) -> list[StageRecord]:
        """Return all :class:`StageRecord` objects for *run_id*.

        Returns an empty list when no matching run exists.

        Raises:
            sqlite3.Error: The query failed.
        """
        try:
            rows = self._conn.execute(
                """
                SELECT run_id, stage_name, status, finding_count
                FROM   stage_results
                WHERE  run_id = ?
                ORDER BY id
                """,
                (run_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise sqlite3.Error(
                f"get_stage_results failed for run_id={run_id!r}: {exc}"
            ) from exc

        return [
            StageRecord(
                run_id=row["run_id"],
                stage_name=row["stage_name"],
                status=row["status"],
                finding_count=row["finding_count"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Read — findings for a run
    # ------------------------------------------------------------------

    def get_findings(self, run_id: str) -> list[FindingRecord]:
        """Return all :class:`FindingRecord` objects for *run_id*.

        Returns an empty list when no matching run exists.

        Raises:
            sqlite3.Error: The query failed.
        """
        try:
            rows = self._conn.execute(
                """
                SELECT run_id, stage_name, rule_id, status,
                       message, affected_row_count,
                       affected_rows, metadata_json
                FROM   findings
                WHERE  run_id = ?
                ORDER BY id
                """,
                (run_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise sqlite3.Error(
                f"get_findings failed for run_id={run_id!r}: {exc}"
            ) from exc

        return [_row_to_finding_record(row) for row in rows]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_affected_rows(raw: str) -> tuple[int, ...]:
    """Parse a space-separated integer string back to a tuple."""
    if not raw or not raw.strip():
        return ()
    try:
        return tuple(int(x) for x in raw.split())
    except ValueError:
        return ()


def _parse_metadata(raw: str) -> dict[str, Any]:
    """Parse a JSON string back to a dict; return {} on failure."""
    if not raw or raw == "{}":
        return {}
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        return {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _row_to_run_record(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        dataset_name=row["dataset_name"],
        recorded_at=row["recorded_at"],
        overall_status=row["overall_status"],
        quality_score=row["quality_score"],
        total_findings=row["total_findings"],
        pass_count=row["pass_count"],
        warning_count=row["warning_count"],
        fail_count=row["fail_count"],
        summary=row["summary"],
    )


def _row_to_run_summary(row: sqlite3.Row) -> RunSummary:
    return RunSummary(
        run_id=row["run_id"],
        dataset_name=row["dataset_name"],
        recorded_at=row["recorded_at"],
        overall_status=row["overall_status"],
        quality_score=row["quality_score"],
        total_findings=row["total_findings"],
        pass_count=row["pass_count"],
        warning_count=row["warning_count"],
        fail_count=row["fail_count"],
    )


def _row_to_finding_record(row: sqlite3.Row) -> FindingRecord:
    return FindingRecord(
        run_id=row["run_id"],
        stage_name=row["stage_name"],
        rule_id=row["rule_id"],
        status=row["status"],
        message=row["message"],
        affected_row_count=row["affected_row_count"],
        affected_rows=_parse_affected_rows(row["affected_rows"]),
        metadata=_parse_metadata(row["metadata_json"]),
    )
