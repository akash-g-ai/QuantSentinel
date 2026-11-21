"""Quality assessment stage.

Rolls the findings from every validation stage into a transparent, traceable
quality verdict.  The original :class:`~quantsentinel.models.ValidationReport`
and all its stage findings are preserved unchanged.

Public interface
----------------
    assess_quality(report: ValidationReport) -> AssessedReport

Scoring formula
---------------
Each finding contributes a penalty based on its status:

    FAIL finding    → 10 penalty points
    WARNING finding →  3 penalty points
    PASS finding    →  0 penalty points

    score = max(0, 100 - total_penalty)

The formula is deterministic and fully traceable: the score for any dataset
can be reproduced by counting FAIL and WARNING findings and applying the
formula above.  The score never exceeds 100 or falls below 0.

Overall status
--------------
    FAIL    if any stage contains at least one FAIL finding.
    WARNING if no FAIL exists but at least one WARNING exists.
    PASS    if every finding is PASS (or no findings exist).

Design constraints
------------------
- ``models.py`` is not modified.
- The input ``ValidationReport`` and all its stage findings are never altered.
- No pandas, numpy, or third-party imports.
- No Streamlit, Plotly, or database imports.
- No hidden weights or opaque calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from quantsentinel.models import (
    Finding,
    StageResult,
    ValidationReport,
    ValidationStatus,
)

# ---------------------------------------------------------------------------
# Scoring weights (documented here, used only here)
# ---------------------------------------------------------------------------

_PENALTY_FAIL: Final[int] = 10
_PENALTY_WARNING: Final[int] = 3


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StatusCounts:
    """Finding counts grouped by severity.

    Attributes
    ----------
    pass_count:    Number of PASS findings across all stages.
    warning_count: Number of WARNING findings across all stages.
    fail_count:    Number of FAIL findings across all stages.
    total:         Sum of all three counts.
    """

    pass_count: int
    warning_count: int
    fail_count: int

    @property
    def total(self) -> int:
        return self.pass_count + self.warning_count + self.fail_count


@dataclass(frozen=True)
class QualityAssessment:
    """The quality verdict for one pipeline run.

    This object is immutable and self-contained.  Every field that
    contributes to the score or verdict is stored explicitly so the result
    can be audited without re-running the pipeline.

    Attributes
    ----------
    overall_status:
        The worst :class:`~quantsentinel.models.ValidationStatus` across all
        stage results.
    score:
        Integer quality score in the range [0, 100].
        ``score = max(0, 100 - total_penalty)`` where
        ``total_penalty = (fail_count × 10) + (warning_count × 3)``.
    total_penalty:
        The raw penalty before clamping.  Stored for full traceability.
    status_counts:
        Finding counts grouped by severity.
    summary:
        Human-readable explanation of the overall status and score.
    penalty_per_fail:
        The penalty weight applied to each FAIL finding (always 10).
    penalty_per_warning:
        The penalty weight applied to each WARNING finding (always 3).
    """

    overall_status: ValidationStatus
    score: int
    total_penalty: int
    status_counts: StatusCounts
    summary: str
    penalty_per_fail: int = field(default=_PENALTY_FAIL)
    penalty_per_warning: int = field(default=_PENALTY_WARNING)


@dataclass(frozen=True)
class AssessedReport:
    """A :class:`~quantsentinel.models.ValidationReport` paired with its quality assessment.

    The original report is stored by reference; none of its data is copied or
    modified.  All stage results and individual findings remain accessible
    through ``report.stage_results``.

    Attributes
    ----------
    report:
        The original :class:`~quantsentinel.models.ValidationReport` produced
        by the pipeline.  Unchanged.
    assessment:
        The :class:`QualityAssessment` derived from the report's findings.
    """

    report: ValidationReport
    assessment: QualityAssessment


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def assess_quality(report: ValidationReport) -> AssessedReport:
    """Assess the quality of a completed validation run.

    Reads every finding in every stage of *report*, computes the quality
    score and overall status, and returns an :class:`AssessedReport` that
    pairs the original report with a :class:`QualityAssessment`.

    The input *report* is never modified.

    Args:
        report: A fully assembled :class:`~quantsentinel.models.ValidationReport`
                returned by the pipeline after all validation stages have run.

    Returns:
        An :class:`AssessedReport` containing the original report and a
        :class:`QualityAssessment` with score, status, counts, and summary.

    Raises:
        TypeError: *report* is not a
                   :class:`~quantsentinel.models.ValidationReport`.
    """
    if not isinstance(report, ValidationReport):
        raise TypeError(
            f"assess_quality expects a ValidationReport, got {type(report)!r}"
        )

    all_findings = _collect_findings(report)
    counts = _count_by_status(all_findings)
    overall_status = _derive_overall_status(counts)
    total_penalty, score = _compute_score(counts)
    summary = _build_summary(report, overall_status, score, counts)

    assessment = QualityAssessment(
        overall_status=overall_status,
        score=score,
        total_penalty=total_penalty,
        status_counts=counts,
        summary=summary,
    )

    return AssessedReport(report=report, assessment=assessment)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_findings(report: ValidationReport) -> list[Finding]:
    """Return a flat list of every finding across all stages."""
    findings: list[Finding] = []
    for stage in report.stage_results:
        findings.extend(stage.findings)
    return findings


def _count_by_status(findings: list[Finding]) -> StatusCounts:
    """Count findings grouped by ValidationStatus."""
    pass_count = sum(1 for f in findings if f.status == ValidationStatus.PASS)
    warning_count = sum(1 for f in findings if f.status == ValidationStatus.WARNING)
    fail_count = sum(1 for f in findings if f.status == ValidationStatus.FAIL)
    return StatusCounts(
        pass_count=pass_count,
        warning_count=warning_count,
        fail_count=fail_count,
    )


def _derive_overall_status(counts: StatusCounts) -> ValidationStatus:
    """Determine overall status from severity counts.

    FAIL   if any FAIL findings exist.
    WARNING if no FAIL but at least one WARNING exists.
    PASS   if no FAIL and no WARNING findings exist.
    """
    if counts.fail_count > 0:
        return ValidationStatus.FAIL
    if counts.warning_count > 0:
        return ValidationStatus.WARNING
    return ValidationStatus.PASS


def _compute_score(counts: StatusCounts) -> tuple[int, int]:
    """Return (total_penalty, score).

    Scoring formula:
        total_penalty = (fail_count × 10) + (warning_count × 3)
        score         = max(0, 100 - total_penalty)
    """
    total_penalty = (
        counts.fail_count * _PENALTY_FAIL
        + counts.warning_count * _PENALTY_WARNING
    )
    score = max(0, 100 - total_penalty)
    return total_penalty, score


def _build_summary(
    report: ValidationReport,
    overall_status: ValidationStatus,
    score: int,
    counts: StatusCounts,
) -> str:
    """Compose a concise human-readable quality summary."""

    # Opening sentence.
    if overall_status == ValidationStatus.PASS:
        verdict = (
            f"Dataset '{report.dataset_name}' passed all validation checks."
        )
    elif overall_status == ValidationStatus.WARNING:
        verdict = (
            f"Dataset '{report.dataset_name}' passed with warnings. "
            "Review flagged items before use."
        )
    else:
        verdict = (
            f"Dataset '{report.dataset_name}' failed validation. "
            "FAIL findings must be resolved before the dataset can be used."
        )

    # Finding breakdown.
    breakdown = (
        f"Findings: {counts.total} total — "
        f"{counts.fail_count} FAIL, "
        f"{counts.warning_count} WARNING, "
        f"{counts.pass_count} PASS."
    )

    # Score explanation.
    penalty_detail = (
        f"Penalty: ({counts.fail_count} × {_PENALTY_FAIL}) + "
        f"({counts.warning_count} × {_PENALTY_WARNING}) = "
        f"{counts.fail_count * _PENALTY_FAIL + counts.warning_count * _PENALTY_WARNING} pt(s). "
        f"Quality score: {score}/100."
    )

    return f"{verdict} {breakdown} {penalty_detail}"
