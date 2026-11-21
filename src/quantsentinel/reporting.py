"""Research-ready output and reporting.

Accepts the :class:`~quantsentinel.quality.AssessedReport` produced by the
pipeline and generates human-readable summaries, structured JSON, and flat
CSV exports.  The original dataset and all validation results are never
modified.

Public interface
----------------
    build_text_summary(assessed: AssessedReport) -> str
    to_json(assessed: AssessedReport) -> str
    to_csv(assessed: AssessedReport) -> str
    save_text_summary(assessed: AssessedReport, path: str | Path) -> Path
    save_json(assessed: AssessedReport, path: str | Path) -> Path
    save_csv(assessed: AssessedReport, path: str | Path) -> Path

Design constraints
------------------
- AssessedReport, ValidationReport, and all findings are read-only.
- Output is written to caller-provided paths only; ``data/raw`` is never
  written to.
- Standard library only: ``json``, ``csv``, ``io``, ``pathlib``, ``datetime``.
- No pandas, numpy, Streamlit, Plotly, or database imports.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from quantsentinel.quality import AssessedReport, QualityAssessment


# ---------------------------------------------------------------------------
# Public — text summary
# ---------------------------------------------------------------------------

def build_text_summary(assessed: AssessedReport) -> str:
    """Return a multi-line human-readable validation summary.

    The summary contains:
    - Dataset name and overall status
    - Quality score and finding counts
    - Stage-wise status and finding counts
    - Individual findings with rule ID, status, message, and affected rows

    Args:
        assessed: The :class:`~quantsentinel.quality.AssessedReport` returned
                  by :func:`~quantsentinel.pipeline.run_pipeline`.

    Returns:
        A plain-text string suitable for printing or writing to a ``.txt`` file.

    Raises:
        TypeError: *assessed* is not an :class:`~quantsentinel.quality.AssessedReport`.
    """
    _require_assessed_report(assessed)

    report = assessed.report
    qa = assessed.assessment
    counts = qa.status_counts
    lines: list[str] = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    lines.append("=" * 72)
    lines.append("QuantSentinel Validation Report")
    lines.append("=" * 72)
    lines.append(f"Dataset       : {report.dataset_name}")
    lines.append(f"Overall status: {qa.overall_status.name}")
    lines.append(f"Quality score : {qa.score}/100")
    lines.append(f"Generated     : {_utc_now()}")
    lines.append("")

    # ------------------------------------------------------------------
    # Finding counts
    # ------------------------------------------------------------------
    lines.append("Finding summary")
    lines.append("-" * 40)
    lines.append(f"  Total    : {counts.total}")
    lines.append(f"  FAIL     : {counts.fail_count}")
    lines.append(f"  WARNING  : {counts.warning_count}")
    lines.append(f"  PASS     : {counts.pass_count}")
    lines.append("")

    # Scoring formula — explicit so the reader can verify the number.
    lines.append("Score formula")
    lines.append("-" * 40)
    lines.append(
        f"  Penalty = "
        f"({counts.fail_count} FAIL × {qa.penalty_per_fail} pt) + "
        f"({counts.warning_count} WARNING × {qa.penalty_per_warning} pt) "
        f"= {qa.total_penalty} pt"
    )
    lines.append(f"  Score   = max(0, 100 − {qa.total_penalty}) = {qa.score}")
    lines.append("")

    # ------------------------------------------------------------------
    # Stage-wise breakdown
    # ------------------------------------------------------------------
    lines.append("Stage results")
    lines.append("-" * 40)

    if not report.stage_results:
        lines.append("  No stages were executed.")
    else:
        for stage in report.stage_results:
            stage_counts = _stage_counts(stage)
            lines.append(
                f"  {stage.stage_name:<20} "
                f"status={stage.status.name:<8} "
                f"findings={stage.finding_count} "
                f"(FAIL={stage_counts['fail']}, "
                f"WARN={stage_counts['warning']}, "
                f"PASS={stage_counts['pass']})"
            )
    lines.append("")

    # ------------------------------------------------------------------
    # Individual findings per stage
    # ------------------------------------------------------------------
    lines.append("Individual findings")
    lines.append("=" * 72)

    if not report.stage_results:
        lines.append("  None.")
    else:
        for stage in report.stage_results:
            lines.append(f"\n[Stage: {stage.stage_name}]")
            lines.append("-" * 40)
            if not stage.findings:
                lines.append("  No findings.")
                continue
            for finding in stage.findings:
                lines.append(f"  Rule    : {finding.rule_id}")
                lines.append(f"  Status  : {finding.status.name}")
                lines.append(f"  Message : {finding.message}")
                if finding.affected_rows:
                    rows_preview = _format_rows_preview(finding.affected_rows)
                    lines.append(f"  Rows    : {rows_preview}")
                if finding.metadata:
                    lines.append(f"  Metadata: {_format_metadata(finding.metadata)}")
                lines.append("")

    lines.append("=" * 72)
    lines.append("End of report")
    lines.append("=" * 72)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public — JSON export
# ---------------------------------------------------------------------------

def to_json(assessed: AssessedReport) -> str:
    """Serialise *assessed* to a JSON string.

    The JSON structure preserves all report fields, all stage results, every
    individual finding (rule_id, status, message, affected_rows, metadata),
    and the full quality assessment.

    Args:
        assessed: The :class:`~quantsentinel.quality.AssessedReport` to serialise.

    Returns:
        A UTF-8 JSON string with 2-space indentation.

    Raises:
        TypeError: *assessed* is not an :class:`~quantsentinel.quality.AssessedReport`.
    """
    _require_assessed_report(assessed)
    return json.dumps(_assessed_to_dict(assessed), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public — CSV export
# ---------------------------------------------------------------------------

def to_csv(assessed: AssessedReport) -> str:
    """Serialise findings to a flat CSV string.

    Each row in the output represents one :class:`~quantsentinel.models.Finding`.
    Columns:

    ``stage``, ``rule_id``, ``status``, ``message``,
    ``affected_row_count``, ``affected_rows``, ``metadata``

    ``affected_rows`` is a space-separated list of integers.
    ``metadata`` is a JSON-encoded string so it fits a single cell.

    Args:
        assessed: The :class:`~quantsentinel.quality.AssessedReport` to export.

    Returns:
        A CSV-formatted string including a header row.

    Raises:
        TypeError: *assessed* is not an :class:`~quantsentinel.quality.AssessedReport`.
    """
    _require_assessed_report(assessed)

    fieldnames = [
        "stage",
        "rule_id",
        "status",
        "message",
        "affected_row_count",
        "affected_rows",
        "metadata",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        lineterminator="\n",
        quoting=csv.QUOTE_ALL,
    )
    writer.writeheader()

    for stage in assessed.report.stage_results:
        for finding in stage.findings:
            writer.writerow({
                "stage": stage.stage_name,
                "rule_id": finding.rule_id,
                "status": finding.status.name,
                "message": finding.message,
                "affected_row_count": len(finding.affected_rows),
                "affected_rows": " ".join(str(r) for r in finding.affected_rows),
                "metadata": json.dumps(finding.metadata, ensure_ascii=False)
                            if finding.metadata else "",
            })

    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Public — save helpers
# ---------------------------------------------------------------------------

def save_text_summary(assessed: AssessedReport, path: str | Path) -> Path:
    """Write the text summary to *path* and return the resolved :class:`Path`.

    The parent directory must already exist.

    Raises:
        TypeError:          *assessed* is not an ``AssessedReport``.
        FileNotFoundError:  The parent directory of *path* does not exist.
    """
    _require_assessed_report(assessed)
    dest = _require_parent(path)
    dest.write_text(build_text_summary(assessed), encoding="utf-8")
    return dest


def save_json(assessed: AssessedReport, path: str | Path) -> Path:
    """Write the JSON export to *path* and return the resolved :class:`Path`.

    The parent directory must already exist.

    Raises:
        TypeError:          *assessed* is not an ``AssessedReport``.
        FileNotFoundError:  The parent directory of *path* does not exist.
    """
    _require_assessed_report(assessed)
    dest = _require_parent(path)
    dest.write_text(to_json(assessed), encoding="utf-8")
    return dest


def save_csv(assessed: AssessedReport, path: str | Path) -> Path:
    """Write the CSV export to *path* and return the resolved :class:`Path`.

    The parent directory must already exist.

    Raises:
        TypeError:          *assessed* is not an ``AssessedReport``.
        FileNotFoundError:  The parent directory of *path* does not exist.
    """
    _require_assessed_report(assessed)
    dest = _require_parent(path)
    dest.write_text(to_csv(assessed), encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Internal serialisation helpers
# ---------------------------------------------------------------------------

def _assessed_to_dict(assessed: AssessedReport) -> dict[str, Any]:
    """Convert an AssessedReport to a plain dict for JSON serialisation."""
    report = assessed.report
    qa = assessed.assessment
    counts = qa.status_counts

    return {
        "generated_at": _utc_now(),
        "dataset_name": report.dataset_name,
        "overall_status": qa.overall_status.name,
        "quality_score": qa.score,
        "total_penalty": qa.total_penalty,
        "scoring": {
            "penalty_per_fail": qa.penalty_per_fail,
            "penalty_per_warning": qa.penalty_per_warning,
            "formula": "score = max(0, 100 - total_penalty)",
        },
        "finding_counts": {
            "total": counts.total,
            "fail": counts.fail_count,
            "warning": counts.warning_count,
            "pass": counts.pass_count,
        },
        "summary": qa.summary,
        "stages": [
            _stage_to_dict(stage) for stage in report.stage_results
        ],
    }


def _stage_to_dict(stage: StageResult) -> dict[str, Any]:
    """Convert a StageResult to a plain dict."""
    stage_counts = _stage_counts(stage)
    return {
        "stage_name": stage.stage_name,
        "status": stage.status.name,
        "finding_count": stage.finding_count,
        "finding_counts": stage_counts,
        "findings": [_finding_to_dict(f) for f in stage.findings],
    }


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Convert a Finding to a plain dict."""
    return {
        "rule_id": finding.rule_id,
        "status": finding.status.name,
        "message": finding.message,
        "affected_row_count": len(finding.affected_rows),
        "affected_rows": list(finding.affected_rows),
        "metadata": finding.metadata,
    }


def _stage_counts(stage: StageResult) -> dict[str, int]:
    """Return per-status counts for one stage."""
    from quantsentinel.models import ValidationStatus
    return {
        "fail":    sum(1 for f in stage.findings if f.status == ValidationStatus.FAIL),
        "warning": sum(1 for f in stage.findings if f.status == ValidationStatus.WARNING),
        "pass":    sum(1 for f in stage.findings if f.status == ValidationStatus.PASS),
    }


# ---------------------------------------------------------------------------
# Internal formatting helpers
# ---------------------------------------------------------------------------

def _format_rows_preview(rows: tuple[int, ...], limit: int = 10) -> str:
    """Format affected row indices as a compact string with optional truncation."""
    if len(rows) <= limit:
        return str(list(rows))
    shown = list(rows[:limit])
    return f"{shown} … and {len(rows) - limit} more"


def _format_metadata(metadata: dict[str, Any]) -> str:
    """Format metadata as a compact single-line JSON string."""
    try:
        return json.dumps(metadata, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(metadata)


def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Internal guards
# ---------------------------------------------------------------------------

def _require_assessed_report(assessed: object) -> None:
    if not isinstance(assessed, AssessedReport):
        raise TypeError(
            f"Expected an AssessedReport, got {type(assessed)!r}"
        )


def _require_parent(path: str | Path) -> Path:
    """Resolve *path* and verify its parent directory exists."""
    dest = Path(path)
    if not dest.parent.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {dest.parent}"
        )
    return dest
