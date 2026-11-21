"""Statistical validation stage.

Detects statistically unusual market observations that may require researcher
attention.  Anomalies are flagged as WARNING — they are not treated as errors,
and the original uploaded values are always preserved.

Public interface
----------------
    validate_statistics(
        data: pd.DataFrame,
        *,
        return_threshold: float = 0.20,
        volume_window: int = 20,
        volume_z_threshold: float = 3.0,
        mad_z_threshold: float = 3.5,
    ) -> StageResult

Rules
-----
ABNORMAL_RETURNS   WARNING  A daily close-to-close return exceeds
                             ``return_threshold`` in absolute value.
VOLUME_SPIKE       WARNING  Daily volume exceeds the rolling mean by more
                             than ``volume_z_threshold`` rolling standard
                             deviations over a ``volume_window``-day window.
RETURN_OUTLIERS    WARNING  A daily return is an extreme outlier as measured
                             by the Median Absolute Deviation (MAD) method,
                             scaled by ``mad_z_threshold``.

Design constraints
------------------
- The source DataFrame is never modified.
- SciPy is not used; all statistics use pandas / numpy.
- No Streamlit, Plotly, or database imports.
- No price predictions or trading recommendations.
- No new dependencies are added.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

from quantsentinel.models import Finding, StageResult, ValidationStatus

# ---------------------------------------------------------------------------

#: Absolute daily return above which a row is flagged as ABNORMAL_RETURNS.
_DEFAULT_RETURN_THRESHOLD: Final[float] = 0.20   # 20 %

#: Number of trading observations in the rolling window for volume analysis.
_DEFAULT_VOLUME_WINDOW: Final[int] = 20

#: How many rolling standard deviations above the rolling mean a volume
#: observation must be to trigger a VOLUME_SPIKE warning.
_DEFAULT_VOLUME_Z_THRESHOLD: Final[float] = 3.0

#: Modified Z-score threshold for MAD-based return outlier detection.
#: 3.5 is the value recommended by Iglewicz & Hoaglin (1993).
_DEFAULT_MAD_Z_THRESHOLD: Final[float] = 3.5

#: Minimum number of rows needed before return-based rules are meaningful.
_MIN_ROWS_FOR_RETURNS: Final[int] = 2


# ---------------------------------------------------------------------------

def validate_statistics(
    data: pd.DataFrame,
    *,
    return_threshold: float = _DEFAULT_RETURN_THRESHOLD,
    volume_window: int = _DEFAULT_VOLUME_WINDOW,
    volume_z_threshold: float = _DEFAULT_VOLUME_Z_THRESHOLD,
    mad_z_threshold: float = _DEFAULT_MAD_Z_THRESHOLD,
) -> StageResult:
    """Run all statistical checks on *data* and return a :class:`StageResult`.

    All rules produce a WARNING when anomalies are found; none produce a FAIL.
    The source DataFrame is read-only throughout.

    Args:
        data:               DataFrame from ingestion.  Should have a ``Close``
                            column and a ``Volume`` column (case-insensitive).
        return_threshold:   Absolute daily return fraction above which a row
                            is flagged by ABNORMAL_RETURNS.  Default ``0.20``
                            (20 %).  Must be positive.
        volume_window:      Rolling window length (in trading observations)
                            used for VOLUME_SPIKE.  Default ``20``.
                            Must be >= 2.
        volume_z_threshold: Number of rolling standard deviations above the
                            rolling mean that qualifies as a spike.
                            Default ``3.0``.  Must be positive.
        mad_z_threshold:    Modified Z-score threshold for RETURN_OUTLIERS.
                            Default ``3.5``.  Must be positive.

    Returns:
        A :class:`StageResult` with ``stage_name="statistical"`` and one
        :class:`Finding` per rule.

    Raises:
        TypeError:  *data* is not a :class:`pandas.DataFrame`.
        ValueError: Any threshold or window parameter is out of range.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            f"validate_statistics expects a pandas DataFrame, "
            f"got {type(data)!r}"
        )
    _validate_params(return_threshold, volume_window, volume_z_threshold, mad_z_threshold)

    column_map = _resolve_column_map(data)

    returns_series, returns_error = _compute_returns(data, column_map)

    findings: list[Finding] = [
        _check_abnormal_returns(
            data, returns_series, returns_error, return_threshold
        ),
        _check_volume_spike(
            data, column_map, volume_window, volume_z_threshold
        ),
        _check_return_outliers(
            data, returns_series, returns_error, mad_z_threshold
        ),
    ]

    return StageResult(stage_name="statistical", findings=findings)


# ---------------------------------------------------------------------------

def _validate_params(
    return_threshold: float,
    volume_window: int,
    volume_z_threshold: float,
    mad_z_threshold: float,
) -> None:
    if return_threshold <= 0:
        raise ValueError(
            f"return_threshold must be positive, got {return_threshold}"
        )
    if volume_window < 2:
        raise ValueError(
            f"volume_window must be >= 2, got {volume_window}"
        )
    if volume_z_threshold <= 0:
        raise ValueError(
            f"volume_z_threshold must be positive, got {volume_z_threshold}"
        )
    if mad_z_threshold <= 0:
        raise ValueError(
            f"mad_z_threshold must be positive, got {mad_z_threshold}"
        )


# ---------------------------------------------------------------------------

def _resolve_column_map(data: pd.DataFrame) -> dict[str, str]:
    """Map canonical names to actual DataFrame column names (case-insensitive)."""
    actual_lower: dict[str, str] = {col.lower(): col for col in data.columns}
    result: dict[str, str] = {}
    for canonical in ("Close", "Volume", "Date"):
        actual = actual_lower.get(canonical.lower())
        if actual is not None:
            result[canonical] = actual
    return result


# ---------------------------------------------------------------------------

def _compute_returns(
    data: pd.DataFrame,
    column_map: dict[str, str],
) -> tuple[pd.Series | None, str | None]:
    """Compute percentage daily close-to-close returns.

    Returns a tuple of (returns_series, error_message).
    If returns cannot be computed, returns_series is None and error_message
    explains why.  The source DataFrame is never modified.
    """
    actual = column_map.get("Close")
    if actual is None:
        return None, "Close column not found."

    close = _to_numeric_series(data[actual])

    if close.notna().sum() < _MIN_ROWS_FOR_RETURNS:
        return None, (
            f"Fewer than {_MIN_ROWS_FOR_RETURNS} valid Close values; "
            "return calculation not applicable."
        )

    returns = close.pct_change()
    return returns, None


# ---------------------------------------------------------------------------

def _check_abnormal_returns(
    data: pd.DataFrame,
    returns: pd.Series | None,
    error: str | None,
    threshold: float,
) -> Finding:
    """ABNORMAL_RETURNS — absolute daily return > threshold."""
    if returns is None:
        return Finding(
            rule_id="ABNORMAL_RETURNS",
            status=ValidationStatus.WARNING,
            message=f"Abnormal return check skipped: {error}",
        )

    evaluable = returns.notna()
    flagged_mask = evaluable & (returns.abs() > threshold)

    if not flagged_mask.any():
        return Finding(
            rule_id="ABNORMAL_RETURNS",
            status=ValidationStatus.PASS,
            message=(
                f"No abnormal daily returns detected "
                f"(threshold: ±{threshold:.0%})."
            ),
        )

    affected_rows = tuple(data.index[flagged_mask].tolist())
    flagged_returns = returns[flagged_mask]
    max_abs = float(flagged_returns.abs().max())

    sample = {
        str(idx): f"{val:.4%}"
        for idx, val in flagged_returns.items()
    }

    return Finding(
        rule_id="ABNORMAL_RETURNS",
        status=ValidationStatus.WARNING,
        message=(
            f"{len(affected_rows)} row(s) have an absolute daily return "
            f"exceeding {threshold:.0%}. "
            f"Largest observed: {max_abs:.4%}. "
            "Review for data errors or genuine market events."
        ),
        affected_rows=affected_rows,
        metadata={
            "threshold": threshold,
            "max_abs_return": round(max_abs, 6),
            "flagged_returns": sample,
        },
    )


# ---------------------------------------------------------------------------

def _check_volume_spike(
    data: pd.DataFrame,
    column_map: dict[str, str],
    window: int,
    z_threshold: float,
) -> Finding:
    """VOLUME_SPIKE — volume more than z_threshold rolling std above rolling mean."""
    actual = column_map.get("Volume")
    if actual is None:
        return Finding(
            rule_id="VOLUME_SPIKE",
            status=ValidationStatus.WARNING,
            message="Volume spike check skipped: Volume column not found.",
        )

    volume = _to_numeric_series(data[actual])
    n_valid = int(volume.notna().sum())

    min_required = window + 1
    if n_valid < min_required:
        return Finding(
            rule_id="VOLUME_SPIKE",
            status=ValidationStatus.WARNING,
            message=(
                f"Volume spike check skipped: only {n_valid} valid observation(s) "
                f"available; need at least {min_required} for a {window}-period "
                "rolling window."
            ),
        )

    rolling_mean = volume.rolling(window=window, min_periods=window).mean()
    rolling_std  = volume.rolling(window=window, min_periods=window).std(ddof=1)
    rolling_std_safe = rolling_std.where(rolling_std > 0, other=float("nan"))

    z_scores = (volume - rolling_mean) / rolling_std_safe

    evaluable = z_scores.notna()
    flagged_mask = evaluable & (z_scores > z_threshold)

    if not flagged_mask.any():
        return Finding(
            rule_id="VOLUME_SPIKE",
            status=ValidationStatus.PASS,
            message=(
                f"No unusual volume spikes detected "
                f"(window: {window}, threshold: {z_threshold}σ)."
            ),
        )

    affected_rows = tuple(data.index[flagged_mask].tolist())
    max_z = float(z_scores[flagged_mask].max())

    sample_z = {
        str(idx): round(float(z), 4)
        for idx, z in z_scores[flagged_mask].items()
    }

    return Finding(
        rule_id="VOLUME_SPIKE",
        status=ValidationStatus.WARNING,
        message=(
            f"{len(affected_rows)} row(s) have volume more than "
            f"{z_threshold}σ above the {window}-period rolling mean. "
            f"Largest Z-score: {max_z:.4f}. "
            "Review for data errors or genuine volume events."
        ),
        affected_rows=affected_rows,
        metadata={
            "rolling_window": window,
            "z_threshold": z_threshold,
            "max_z_score": round(max_z, 4),
            "flagged_z_scores": sample_z,
        },
    )


# ---------------------------------------------------------------------------

def _check_return_outliers(
    data: pd.DataFrame,
    returns: pd.Series | None,
    error: str | None,
    mad_z_threshold: float,
) -> Finding:
    """RETURN_OUTLIERS — extreme returns by Median Absolute Deviation."""
    if returns is None:
        return Finding(
            rule_id="RETURN_OUTLIERS",
            status=ValidationStatus.WARNING,
            message=f"Return outlier check skipped: {error}",
        )

    valid_returns = returns.dropna()
    n = len(valid_returns)

    if n < _MIN_ROWS_FOR_RETURNS:
        return Finding(
            rule_id="RETURN_OUTLIERS",
            status=ValidationStatus.WARNING,
            message=(
                f"Return outlier check skipped: only {n} valid return(s); "
                "insufficient data for MAD calculation."
            ),
        )

    median_ret = float(valid_returns.median())
    deviations = (valid_returns - median_ret).abs()
    mad = float(deviations.median())

    if mad == 0.0:
        std = float(valid_returns.std(ddof=1))
        if std == 0.0:
            return Finding(
                rule_id="RETURN_OUTLIERS",
                status=ValidationStatus.PASS,
                message=(
                    "No return outliers detected. "
                    "MAD and standard deviation are both zero."
                ),
            )
        modified_z = (valid_returns - median_ret).abs() * 0.6745 / std
        fallback_note = " (MAD was zero; std used)"
    else:
        modified_z = (valid_returns - median_ret).abs() * 0.6745 / mad
        fallback_note = ""

    modified_z_aligned = modified_z.reindex(returns.index)

    evaluable = modified_z_aligned.notna()
    flagged_mask = evaluable & (modified_z_aligned > mad_z_threshold)

    if not flagged_mask.any():
        return Finding(
            rule_id="RETURN_OUTLIERS",
            status=ValidationStatus.PASS,
            message=(
                f"No return outliers detected "
                f"(MAD method, threshold: {mad_z_threshold}){fallback_note}."
            ),
        )

    affected_rows = tuple(data.index[flagged_mask].tolist())
    max_modified_z = float(modified_z_aligned[flagged_mask].max())

    sample_z = {
        str(idx): round(float(z), 4)
        for idx, z in modified_z_aligned[flagged_mask].items()
    }
    sample_ret = {
        str(idx): f"{float(returns.loc[idx]):.4%}"
        for idx in data.index[flagged_mask]
    }

    return Finding(
        rule_id="RETURN_OUTLIERS",
        status=ValidationStatus.WARNING,
        message=(
            f"{len(affected_rows)} row(s) are extreme return outliers "
            f"(MAD modified Z-score > {mad_z_threshold}){fallback_note}. "
            f"Largest modified Z-score: {max_modified_z:.4f}. "
            "These are flagged for review; original values are preserved."
        ),
        affected_rows=affected_rows,
        metadata={
            "method": "MAD modified Z-score (Iglewicz & Hoaglin, 1993)",
            "threshold": mad_z_threshold,
            "median_return": round(median_ret, 6),
            "mad": round(mad, 6),
            "max_modified_z": round(max_modified_z, 4),
            "flagged_modified_z_scores": sample_z,
            "flagged_returns": sample_ret,
        },
    )


# ---------------------------------------------------------------------------

def _to_numeric_series(series: pd.Series) -> pd.Series:
    """Return a numeric view of *series* without modifying the source."""
    if pd.api.types.is_numeric_dtype(series):
        return series
    return pd.to_numeric(series, errors="coerce")