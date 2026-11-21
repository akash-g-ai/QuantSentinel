"""Shared result types for validation findings.

All validation stages produce :class:`Finding` objects and return a
:class:`StageResult`.  The pipeline assembles those into a final
:class:`ValidationReport`.  No validation rules or pipeline logic live here.

Status semantics
----------------
PASS    The rule is satisfied; no action required.
WARNING The record is suspicious and should be reviewed.  It is not
        automatically rejected.
FAIL    The record is invalid and must be quarantined.

Design constraints
------------------
- Standard-library only (``enum``, ``dataclasses``).
- No dependency on pandas, numpy, or any third-party package.
- No validation logic; these are pure data-carrying types.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

class ValidationStatus(enum.Enum):
    """Three-level severity used consistently across every pipeline stage.

    The numeric ``value`` defines the severity order and is used by the
    roll-up helpers: PASS < WARNING < FAIL.  Callers should compare using
    the enum members (``status == ValidationStatus.FAIL``), not the integers.
    """

    PASS = 0
    WARNING = 1
    FAIL = 2

    # Convenience so that the worst of two statuses is always expressible.
    def __lt__(self, other: ValidationStatus) -> bool:  # type: ignore[override]
        if not isinstance(other, ValidationStatus):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: ValidationStatus) -> bool:  # type: ignore[override]
        if not isinstance(other, ValidationStatus):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: ValidationStatus) -> bool:  # type: ignore[override]
        if not isinstance(other, ValidationStatus):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: ValidationStatus) -> bool:  # type: ignore[override]
        if not isinstance(other, ValidationStatus):
            return NotImplemented
        return self.value >= other.value


# ---------------------------------------------------------------------------
# Individual finding
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    """The result of evaluating a single validation rule.

    Attributes
    ----------
    rule_id:
        Short, stable identifier for the rule that produced this finding,
        e.g. ``"OHLC_CONSISTENCY"`` or ``"MISSING_VALUES"``.  Use uppercase
        with underscores.  This identifier is written to the audit log and
        should not change between releases.
    status:
        Outcome of the rule — ``PASS``, ``WARNING``, or ``FAIL``.
    message:
        Human-readable explanation of the outcome.  For failures, state what
        was wrong.  For passes, a brief confirmation is enough.
    affected_rows:
        Tuple of integer row indices (zero-based, as they appear in the
        ingested DataFrame) that triggered this finding.  Empty tuple when
        the check is dataset-level (not row-specific) or when status is
        ``PASS``.
    metadata:
        Optional key/value pairs for any rule-specific context that does not
        belong in the fixed fields — e.g. ``{"expected": "<=", "found": ">"}``.
        Always a plain ``dict``; never nested dataclasses or pandas objects.
    """

    rule_id: str
    status: ValidationStatus
    message: str
    affected_rows: tuple[int, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rule_id or not self.rule_id.strip():
            raise ValueError("rule_id must be a non-empty string")
        if not isinstance(self.status, ValidationStatus):
            raise TypeError(
                f"status must be a ValidationStatus member, got {type(self.status)!r}"
            )
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")
        if not isinstance(self.affected_rows, tuple):
            raise TypeError(
                "affected_rows must be a tuple of ints; "
                "wrap a list with tuple() before passing it"
            )
        if not all(isinstance(i, int) for i in self.affected_rows):
            raise TypeError("every element of affected_rows must be an int")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")


# ---------------------------------------------------------------------------
# Stage result  (one pipeline stage → many findings)
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Findings produced by one pipeline stage.

    Attributes
    ----------
    stage_name:
        Human-readable label for the stage, e.g. ``"structural"``,
        ``"financial"``, ``"statistical"``.
    findings:
        All :class:`Finding` objects emitted by this stage.  The list may be
        empty when the stage produced no findings (implicit ``PASS``).
    status:
        Read-only property — the worst :class:`ValidationStatus` across all
        findings, or ``PASS`` when the list is empty.
    """

    stage_name: str
    findings: list[Finding] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stage_name or not self.stage_name.strip():
            raise ValueError("stage_name must be a non-empty string")
        if not isinstance(self.findings, list):
            raise TypeError("findings must be a list of Finding objects")

    @property
    def status(self) -> ValidationStatus:
        """Worst severity among all findings; ``PASS`` when findings is empty."""
        if not self.findings:
            return ValidationStatus.PASS
        return max(f.status for f in self.findings)

    @property
    def finding_count(self) -> int:
        """Total number of findings in this stage."""
        return len(self.findings)

    def findings_by_status(
        self, status: ValidationStatus
    ) -> list[Finding]:
        """Return findings whose status matches *status*."""
        return [f for f in self.findings if f.status == status]


# ---------------------------------------------------------------------------
# Validation report  (whole pipeline → all stage results)
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    """Full output of one pipeline run.

    Assembles the :class:`StageResult` from every stage into a single object
    that the reporting module writes and the audit module persists.

    Attributes
    ----------
    dataset_name:
        Filename or label that identifies the input dataset, e.g.
        ``"NIFTY50_2024.csv"``.
    stage_results:
        One :class:`StageResult` per executed pipeline stage, in run order.
    status:
        Read-only property — the worst status across all stage results, or
        ``PASS`` when no stages have run.
    total_findings:
        Read-only property — sum of all findings across every stage.
    """

    dataset_name: str
    stage_results: list[StageResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.dataset_name or not self.dataset_name.strip():
            raise ValueError("dataset_name must be a non-empty string")
        if not isinstance(self.stage_results, list):
            raise TypeError("stage_results must be a list of StageResult objects")

    @property
    def status(self) -> ValidationStatus:
        """Worst status across all stage results; ``PASS`` when empty."""
        if not self.stage_results:
            return ValidationStatus.PASS
        return max(s.status for s in self.stage_results)

    @property
    def total_findings(self) -> int:
        """Total number of findings across every stage."""
        return sum(s.finding_count for s in self.stage_results)

    def get_stage(self, stage_name: str) -> StageResult | None:
        """Return the :class:`StageResult` for *stage_name*, or ``None``."""
        for sr in self.stage_results:
            if sr.stage_name == stage_name:
                return sr
        return None
