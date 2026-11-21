"""Pipeline orchestration.

Runs the validation stages in order — ingestion, structural, financial,
statistical, quality assessment — and returns a fully populated
:class:`~quantsentinel.quality.AssessedReport`.

Public interface
----------------
    run_pipeline(
        path: str | Path,
        *,
        return_threshold: float = 0.20,
        volume_window: int = 20,
        volume_z_threshold: float = 3.0,
        mad_z_threshold: float = 3.5,
    ) -> AssessedReport

Execution order
---------------
1. ``load_csv(path)``               → DataFrame
2. ``validate_structure(data)``     → StageResult  ("structural")
3. ``validate_financial(data)``     → StageResult  ("financial")
4. ``validate_statistics(data)``    → StageResult  ("statistical")
5. Assemble ``ValidationReport``
6. ``assess_quality(report)``       → AssessedReport

Rule logic lives entirely in the stage modules.  This module only sequences
stages and assembles their outputs.

Error handling
--------------
- Ingestion errors (FileNotFoundError, UnsupportedFileTypeError, etc.) are
  not caught; they propagate to the caller with their original types and
  messages.
- An unexpected exception raised inside a validation stage is re-raised as a
  ``PipelineStageError`` that names the failing stage, so the caller can
  distinguish a stage crash from an ingestion problem.

Data integrity
--------------
- The original CSV is opened read-only by ``load_csv``; the pipeline never
  writes to it.
- The loaded DataFrame is passed unchanged to each stage.  Stages are
  individually responsible for not mutating it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantsentinel.anomaly import detect_anomalies
from quantsentinel.financial import validate_financial
from quantsentinel.ingestion import load_csv
from quantsentinel.models import ValidationReport
from quantsentinel.quality import AssessedReport, assess_quality
from quantsentinel.statistical import validate_statistics
from quantsentinel.structural import validate_structure


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class PipelineStageError(Exception):
    """Raised when a validation stage raises an unexpected exception.

    Attributes
    ----------
    stage_name:
        The name of the stage that failed (``"structural"``, ``"financial"``,
        or ``"statistical"``).
    original:
        The original exception that was caught.
    """

    def __init__(self, stage_name: str, original: Exception) -> None:
        super().__init__(
            f"Unexpected error in '{stage_name}' stage: "
            f"{type(original).__name__}: {original}"
        )
        self.stage_name = stage_name
        self.original = original


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    path: str | Path,
    *,
    return_threshold: float = 0.20,
    volume_window: int = 20,
    volume_z_threshold: float = 3.0,
    mad_z_threshold: float = 3.5,
) -> AssessedReport:
    """Load a CSV dataset and run the full validation pipeline.

    Args:
        path:
            Location of the CSV file to validate.  Passed directly to
            :func:`~quantsentinel.ingestion.load_csv`; all ingestion
            exceptions propagate unchanged.
        return_threshold:
            Forwarded to :func:`~quantsentinel.statistical.validate_statistics`.
            Absolute daily return above which a row is flagged as
            ABNORMAL_RETURNS.  Default ``0.20`` (20 %).
        volume_window:
            Forwarded to :func:`~quantsentinel.statistical.validate_statistics`.
            Rolling window length for VOLUME_SPIKE detection.  Default ``20``.
        volume_z_threshold:
            Forwarded to :func:`~quantsentinel.statistical.validate_statistics`.
            Z-score threshold for VOLUME_SPIKE.  Default ``3.0``.
        mad_z_threshold:
            Forwarded to :func:`~quantsentinel.statistical.validate_statistics`.
            Modified Z-score threshold for RETURN_OUTLIERS.  Default ``3.5``.

    Returns:
        An :class:`~quantsentinel.quality.AssessedReport` containing:

        - ``report``     — the :class:`~quantsentinel.models.ValidationReport`
          with all three :class:`~quantsentinel.models.StageResult` objects.
        - ``assessment`` — the :class:`~quantsentinel.quality.QualityAssessment`
          with overall status, score, counts, and summary.

    Raises:
        TypeError:              ``path`` is not a string or
                                :class:`pathlib.Path`.
        FileNotFoundError:      ``path`` does not exist.
        UnsupportedFileTypeError: File is not a ``.csv``.
        PermissionError:        File cannot be opened for reading.
        EmptyDatasetError:      File is empty or contains no parseable CSV.
        UnreadableDatasetError: File is not valid UTF-8 or malformed CSV.
        PipelineStageError:     A validation stage raised an unexpected
                                exception.
    """
    # ------------------------------------------------------------------
    # Step 1 — Ingestion
    # ------------------------------------------------------------------
    # load_csv raises typed IngestionError subclasses on failure; let them
    # propagate so the caller receives a precise, actionable error message.
    data = load_csv(path)

    # Use only the filename as the dataset identifier — do not expose the
    # full filesystem path in reports or audit records.
    dataset_name = Path(path).name

    # ------------------------------------------------------------------
    # Steps 2–4 — Validation stages
    # ------------------------------------------------------------------
    structural_result = _run_stage(
        "structural", lambda: validate_structure(data)
    )
    financial_result = _run_stage(
        "financial", lambda: validate_financial(data)
    )
    statistical_result = _run_stage(
        "statistical",
        lambda: validate_statistics(
            data,
            return_threshold=return_threshold,
            volume_window=volume_window,
            volume_z_threshold=volume_z_threshold,
            mad_z_threshold=mad_z_threshold,
        ),
    )

    # ------------------------------------------------------------------
    # Step 2b — ECOD Anomaly Detection (separate stage)
    # ------------------------------------------------------------------
    anomaly_result = _run_stage(
        "anomaly",
        lambda: _run_anomaly_detection(data),
    )

    # ------------------------------------------------------------------
    # Step 5 — Assemble ValidationReport
    # ------------------------------------------------------------------
    report = ValidationReport(
        dataset_name=dataset_name,
        stage_results=[
            structural_result,
            financial_result,
            statistical_result,
            anomaly_result,
        ],
    )

    # ------------------------------------------------------------------
    # Step 6 — Quality assessment
    # ------------------------------------------------------------------
    return assess_quality(report)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _run_stage(stage_name: str, fn: "Any") -> Any:
    """Execute *fn* and return its result.

    If *fn* raises any exception, re-raise it as a
    :class:`PipelineStageError` that names the failing stage.
    This ensures the caller can tell which stage crashed without
    inspecting the traceback.
    """
    try:
        return fn()
    except Exception as exc:
        raise PipelineStageError(stage_name, exc) from exc


def _run_anomaly_detection(data: "pd.DataFrame") -> Any:
    """Run ECOD anomaly detection and return a StageResult.

    Anomalies are reported as WARNING findings.
    """
    result = detect_anomalies(data)

    from quantsentinel.models import Finding, StageResult, ValidationStatus

    findings = []
    for row_index in result.get('detected_rows', []):
        findings.append(
            Finding(
                rule_id='ANOMALY_ECOD',
                status=ValidationStatus.WARNING,
                message=f"ECOD detected anomalous pattern at row {row_index}",
                affected_rows=tuple([row_index]),
                metadata={'anomaly_type': 'ECOD'},
            )
        )

    return StageResult(
        stage_name='anomaly',
        findings=findings,
    )
