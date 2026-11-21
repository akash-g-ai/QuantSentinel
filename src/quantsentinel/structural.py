"""Structural validation stage.

Checks whether an ingested DataFrame has the expected shape, completeness,
and internal consistency before financial and statistical validation run.

Public interface
----------------
    validate_structure(data: pd.DataFrame) -> StageResult

Rules
-----
REQUIRED_COLUMNS   FAIL    One or more required columns are absent.
MISSING_VALUES     FAIL    Required columns contain NaN / NaT values.
DUPLICATE_RECORDS  WARNING Identical rows appear more than once.
DATA_TYPES         FAIL    A required column cannot be interpreted as the
                           expected type (date or numeric).
TRADING_GAP        WARNING Gaps of more than four consecutive weekdays
                           exist in the Date column.  Weekends are always
                           excluded.  Exchange holidays are not known, so
                           short gaps are not flagged.

Design constraints
------------------
- The source DataFrame is never modified.
- No values are filled, cast, or dropped.
- No dependencies beyond pandas (already in requirements.txt).
- No Streamlit, Plotly, or database imports.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

from quantsentinel.models import Finding, StageResult, ValidationStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical column names, stored in the case used for matching.
REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "Date",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
)

#: Columns that must be numeric (integer or float).
_NUMERIC_COLUMNS: Final[frozenset[str]] = frozenset(
    {"Open", "High", "Low", "Close", "Volume"}
)

#: Maximum number of consecutive *weekday* business days that may be absent
#: before a gap is flagged as WARNING.  Four is intentionally conservative:
#: a single exchange holiday creates a one-day gap; a bridge holiday creates
#: a two-day gap.  Four days covers any single week that includes one or two
#: exchange holidays without false positives.  Longer gaps are genuinely
#: unusual and warrant manual review.
_GAP_WEEKDAY_THRESHOLD: Final[int] = 4


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def validate_structure(data: pd.DataFrame) -> StageResult:
    """Run all structural checks on *data* and return a :class:`StageResult`.

    The source DataFrame is read-only.  Every check operates on a view or a
    separate Series; ``data`` is not mutated at any point.

    Args:
        data: The DataFrame produced by :func:`quantsentinel.ingestion.load_csv`.

    Returns:
        A :class:`StageResult` whose ``stage_name`` is ``"structural"`` and
        whose ``findings`` list contains one :class:`Finding` per rule,
        regardless of whether the rule passed or failed.

    Raises:
        TypeError: *data* is not a :class:`pandas.DataFrame`.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            f"validate_structure expects a pandas DataFrame, got {type(data)!r}"
        )

    # Resolve the mapping from canonical column names to actual column names
    # once, so every sub-check reuses the same resolved names.
    column_map = _resolve_column_map(data)

    findings: list[Finding] = []
    findings.append(_check_required_columns(data, column_map))

    # If required columns are missing, subsequent checks that depend on them
    # would produce misleading results.  Emit a single explanatory finding
    # for each remaining rule and return early.
    if findings[0].status == ValidationStatus.FAIL:
        skip_message = (
            "Skipped: required columns are missing. "
            "Fix REQUIRED_COLUMNS findings first."
        )
        for rule_id in (
            "MISSING_VALUES",
            "DUPLICATE_RECORDS",
            "DATA_TYPES",
            "TRADING_GAP",
        ):
            findings.append(
                Finding(
                    rule_id=rule_id,
                    status=ValidationStatus.WARNING,
                    message=skip_message,
                )
            )
        return StageResult(stage_name="structural", findings=findings)

    findings.append(_check_missing_values(data, column_map))
    findings.append(_check_duplicate_records(data))
    findings.append(_check_data_types(data, column_map))
    findings.append(_check_trading_gaps(data, column_map))

    return StageResult(stage_name="structural", findings=findings)


# ---------------------------------------------------------------------------
# Rule 1 — Required columns
# ---------------------------------------------------------------------------

def _resolve_column_map(data: pd.DataFrame) -> dict[str, str]:
    """Return a mapping from canonical column name to actual column name.

    Matching is case-insensitive.  Only columns that exist in *data* appear
    in the mapping; absent columns are not included.

    Example::

        {"Date": "date", "Open": "OPEN", "Close": "Close", ...}
    """
    actual_lower: dict[str, str] = {col.lower(): col for col in data.columns}
    mapping: dict[str, str] = {}
    for canonical in REQUIRED_COLUMNS:
        actual = actual_lower.get(canonical.lower())
        if actual is not None:
            mapping[canonical] = actual
    return mapping


def _check_required_columns(
    data: pd.DataFrame,
    column_map: dict[str, str],
) -> Finding:
    """REQUIRED_COLUMNS — all six columns must be present (case-insensitive)."""
    missing = [col for col in REQUIRED_COLUMNS if col not in column_map]

    if not missing:
        return Finding(
            rule_id="REQUIRED_COLUMNS",
            status=ValidationStatus.PASS,
            message=(
                f"All required columns present: {', '.join(REQUIRED_COLUMNS)}."
            ),
        )

    return Finding(
        rule_id="REQUIRED_COLUMNS",
        status=ValidationStatus.FAIL,
        message=(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected (case-insensitive): {', '.join(REQUIRED_COLUMNS)}."
        ),
        metadata={"missing_columns": missing},
    )


# ---------------------------------------------------------------------------
# Rule 2 — Missing values
# ---------------------------------------------------------------------------

def _check_missing_values(
    data: pd.DataFrame,
    column_map: dict[str, str],
) -> Finding:
    """MISSING_VALUES — no NaN / NaT in any required column."""
    affected_rows: list[int] = []
    affected_columns: list[str] = []

    for canonical, actual in column_map.items():
        null_mask = data[actual].isna()
        if null_mask.any():
            row_indices = data.index[null_mask].tolist()
            affected_rows.extend(row_indices)
            affected_columns.append(canonical)

    if not affected_columns:
        return Finding(
            rule_id="MISSING_VALUES",
            status=ValidationStatus.PASS,
            message="No missing values found in required columns.",
        )

    # De-duplicate row indices while preserving order.
    seen: set[int] = set()
    unique_rows: list[int] = []
    for idx in affected_rows:
        if idx not in seen:
            seen.add(idx)
            unique_rows.append(idx)

    return Finding(
        rule_id="MISSING_VALUES",
        status=ValidationStatus.FAIL,
        message=(
            f"Missing values found in column(s): {', '.join(affected_columns)}. "
            f"{len(unique_rows)} row(s) affected."
        ),
        affected_rows=tuple(unique_rows),
        metadata={"columns_with_nulls": affected_columns},
    )


# ---------------------------------------------------------------------------
# Rule 3 — Duplicate records
# ---------------------------------------------------------------------------

def _check_duplicate_records(data: pd.DataFrame) -> Finding:
    """DUPLICATE_RECORDS — no row should appear more than once."""
    duplicate_mask = data.duplicated(keep=False)

    if not duplicate_mask.any():
        return Finding(
            rule_id="DUPLICATE_RECORDS",
            status=ValidationStatus.PASS,
            message="No duplicate records found.",
        )

    dup_indices = tuple(data.index[duplicate_mask].tolist())
    return Finding(
        rule_id="DUPLICATE_RECORDS",
        status=ValidationStatus.WARNING,
        message=(
            f"{len(dup_indices)} row(s) are part of duplicate record groups. "
            "Duplicates are preserved; review before proceeding."
        ),
        affected_rows=dup_indices,
    )


# ---------------------------------------------------------------------------
# Rule 4 — Data types
# ---------------------------------------------------------------------------

def _check_data_types(
    data: pd.DataFrame,
    column_map: dict[str, str],
) -> Finding:
    """DATA_TYPES — Date parseable as date; OHLCV columns numeric."""
    type_failures: list[str] = []
    affected_rows: list[int] = []

    # --- Date column ---
    date_actual = column_map.get("Date")
    if date_actual is not None:
        date_col = data[date_actual]
        # Accept columns already typed as datetime.
        if not pd.api.types.is_datetime64_any_dtype(date_col):
            # Try parsing as datetime without modifying the source column.
            try:
                pd.to_datetime(date_col, errors="raise")
            except (ValueError, TypeError):
                type_failures.append(
                    f"Date column '{date_actual}' cannot be parsed as a date."
                )
                unparseable_mask = pd.to_datetime(date_col, errors="coerce").isna()
                affected_rows.extend(data.index[unparseable_mask].tolist())

    # --- Numeric columns (OHLCV) ---
    for canonical in _NUMERIC_COLUMNS:
        actual = column_map.get(canonical)
        if actual is None:
            continue
        col = data[actual]
        if not pd.api.types.is_numeric_dtype(col):
            # Try coercing without touching source data.
            coerced = pd.to_numeric(col, errors="coerce")
            non_numeric_mask = coerced.isna() & col.notna()
            if non_numeric_mask.any():
                type_failures.append(
                    f"Column '{actual}' (expected numeric for {canonical}) "
                    f"contains {non_numeric_mask.sum()} non-numeric value(s)."
                )
                affected_rows.extend(data.index[non_numeric_mask].tolist())

    if not type_failures:
        return Finding(
            rule_id="DATA_TYPES",
            status=ValidationStatus.PASS,
            message="All required columns have expected data types.",
        )

    seen: set[int] = set()
    unique_rows: list[int] = []
    for idx in affected_rows:
        if idx not in seen:
            seen.add(idx)
            unique_rows.append(idx)

    return Finding(
        rule_id="DATA_TYPES",
        status=ValidationStatus.FAIL,
        message=(
            f"Data type issues found in {len(type_failures)} column(s). "
            + " | ".join(type_failures)
        ),
        affected_rows=tuple(unique_rows),
        metadata={"type_failures": type_failures},
    )


# ---------------------------------------------------------------------------
# Rule 5 — Trading-session gaps
# ---------------------------------------------------------------------------

def _check_trading_gaps(
    data: pd.DataFrame,
    column_map: dict[str, str],
) -> Finding:
    """TRADING_GAP — flag unusually long weekday gaps in the Date column.

    Methodology and limitations
    ---------------------------
    A "gap" is the number of weekdays (Monday–Friday) between two consecutive
    dates in the dataset, minus one (the trading day itself).

    - Gaps of 1 weekday  → normal (weekend between consecutive Fridays = gap 2,
      see below, so this handles Mon–Fri back-to-back).
    - Gaps of 2–3 weekdays → plausible exchange holiday bridge; not flagged.
    - Gaps of 4+ weekdays → flagged as WARNING for manual review.

    **This rule does not know any exchange holiday calendar.**  A single-day
    holiday creates a 1-weekday gap (not flagged), a bridge creates a 2-day
    gap (not flagged).  Only gaps long enough to be unusual without a holiday
    explanation are surfaced.

    If the Date column cannot be parsed as dates, or if fewer than two valid
    dates exist, the rule reports the limitation instead of guessing.
    """
    date_actual = column_map.get("Date")
    if date_actual is None:
        return Finding(
            rule_id="TRADING_GAP",
            status=ValidationStatus.WARNING,
            message="Gap analysis skipped: Date column not available.",
        )

    # Attempt to parse without modifying source data.
    try:
        parsed_dates = pd.to_datetime(data[date_actual], errors="raise")
    except (ValueError, TypeError):
        return Finding(
            rule_id="TRADING_GAP",
            status=ValidationStatus.WARNING,
            message=(
                "Gap analysis skipped: Date column could not be parsed as dates. "
                "See DATA_TYPES finding for details."
            ),
        )

    valid_dates = parsed_dates.dropna().sort_values()

    if len(valid_dates) < 2:
        return Finding(
            rule_id="TRADING_GAP",
            status=ValidationStatus.PASS,
            message="Fewer than two valid dates; gap analysis not applicable.",
        )

    # Build a Series of (date, original_index) sorted by date so we can
    # report the gap location by its integer row index in the source frame.
    sorted_pairs = list(
        zip(valid_dates.values, valid_dates.index.tolist())
    )

    gap_descriptions: list[str] = []
    affected_rows: list[int] = []

    for i in range(1, len(sorted_pairs)):
        prev_date, prev_idx = sorted_pairs[i - 1]
        curr_date, curr_idx = sorted_pairs[i]

        # np.busday_count counts weekdays strictly between the two dates.
        # We want weekday distance = business days from prev to curr inclusive
        # of curr but exclusive of prev, i.e. busday_count(prev, curr).
        prev_ts = pd.Timestamp(prev_date)
        curr_ts = pd.Timestamp(curr_date)

        # Number of weekday days from prev (exclusive) to curr (inclusive).
        weekday_gap = pd.bdate_range(
            prev_ts + pd.Timedelta(days=1), curr_ts
        ).size

        if weekday_gap >= _GAP_WEEKDAY_THRESHOLD:
            gap_descriptions.append(
                f"{prev_ts.date()} → {curr_ts.date()} "
                f"({weekday_gap} weekday(s) apart)"
            )
            affected_rows.extend([int(prev_idx), int(curr_idx)])

    if not gap_descriptions:
        return Finding(
            rule_id="TRADING_GAP",
            status=ValidationStatus.PASS,
            message=(
                "No unusual trading-session gaps detected. "
                f"(Threshold: {_GAP_WEEKDAY_THRESHOLD}+ consecutive weekdays.)"
            ),
        )

    seen: set[int] = set()
    unique_rows: list[int] = []
    for idx in affected_rows:
        if idx not in seen:
            seen.add(idx)
            unique_rows.append(idx)

    return Finding(
        rule_id="TRADING_GAP",
        status=ValidationStatus.WARNING,
        message=(
            f"{len(gap_descriptions)} unusual gap(s) found in trading dates. "
            f"Threshold: {_GAP_WEEKDAY_THRESHOLD}+ consecutive weekdays. "
            "Exchange holidays are not modelled; review manually. "
            "Gap(s): " + "; ".join(gap_descriptions) + "."
        ),
        affected_rows=tuple(unique_rows),
        metadata={
            "gap_threshold_weekdays": _GAP_WEEKDAY_THRESHOLD,
            "gaps": gap_descriptions,
            "limitation": (
                "No exchange holiday calendar is applied. "
                "Short gaps (1–3 weekdays) are not flagged."
            ),
        },
    )
