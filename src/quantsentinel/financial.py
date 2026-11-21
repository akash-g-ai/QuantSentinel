"""Financial validation stage.

Checks whether financial market records follow basic financial logic:
OHLC relationships, non-positive prices, volume validity, and trading
date consistency.
"""

from __future__ import annotations

from typing import Final

import pandas as pd

from quantsentinel.models import Finding, StageResult, ValidationStatus

_PRICE_COLUMNS: Final[tuple[str, ...]] = ("Open", "High", "Low", "Close")
_FINANCIAL_COLUMNS: Final[tuple[str, ...]] = ("Date", "Open", "High", "Low", "Close", "Volume")


def validate_financial(data: pd.DataFrame) -> StageResult:
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"validate_financial expects a pandas DataFrame, got {type(data)!r}")

    column_map = _resolve_column_map(data)

    findings: list[Finding] = [
        _check_ohlc_consistency(data, column_map),
        _check_non_positive_prices(data, column_map),
        _check_invalid_volume(data, column_map),
        _check_trading_date_validity(data, column_map),
        _check_duplicate_dates(data, column_map),
    ]

    return StageResult(stage_name="financial", findings=findings)


def _resolve_column_map(data: pd.DataFrame) -> dict[str, str]:
    actual_lower: dict[str, str] = {col.lower(): col for col in data.columns}
    return {
        canonical: actual_lower[canonical.lower()]
        for canonical in _FINANCIAL_COLUMNS
        if canonical.lower() in actual_lower
    }


def _check_ohlc_consistency(data: pd.DataFrame, column_map: dict[str, str]) -> Finding:
    required = ("Open", "High", "Low", "Close")
    missing = [c for c in required if c not in column_map]
    if missing:
        return Finding(
            rule_id="OHLC_CONSISTENCY",
            status=ValidationStatus.WARNING,
            message=f"OHLC consistency check skipped: column(s) not found: {', '.join(missing)}.",
            metadata={"missing_columns": missing},
        )

    open_col = _to_numeric_series(data[column_map["Open"]])
    high_col = _to_numeric_series(data[column_map["High"]])
    low_col = _to_numeric_series(data[column_map["Low"]])
    close_col = _to_numeric_series(data[column_map["Close"]])

    any_null = open_col.isna() | high_col.isna() | low_col.isna() | close_col.isna()
    evaluable = ~any_null

    high_lt_low = evaluable & (high_col < low_col)
    high_lt_open = evaluable & (high_col < open_col)
    high_lt_close = evaluable & (high_col < close_col)
    low_gt_open = evaluable & (low_col > open_col)
    low_gt_close = evaluable & (low_col > close_col)

    invalid_mask = high_lt_low | high_lt_open | high_lt_close | low_gt_open | low_gt_close

    if not invalid_mask.any():
        return Finding(rule_id="OHLC_CONSISTENCY", status=ValidationStatus.PASS, message="All OHLC relationships are consistent.")

    affected_rows = tuple(data.index[invalid_mask].tolist())

    breakdown: dict[str, int] = {}
    for label, mask in (
        ("High < Low", high_lt_low),
        ("High < Open", high_lt_open),
        ("High < Close", high_lt_close),
        ("Low > Open", low_gt_open),
        ("Low > Close", low_gt_close),
    ):
        count = int(mask.sum())
        if count:
            breakdown[label] = count

    return Finding(
        rule_id="OHLC_CONSISTENCY",
        status=ValidationStatus.FAIL,
        message=f"{len(affected_rows)} row(s) have invalid OHLC relationships. Breakdown: " + ", ".join(f"{k}: {v}" for k, v in breakdown.items()) + ".",
        affected_rows=affected_rows,
        metadata={"breakdown": breakdown},
    )


def _check_non_positive_prices(data: pd.DataFrame, column_map: dict[str, str]) -> Finding:
    affected_rows: list[int] = []
    affected_columns: list[str] = []

    for canonical in _PRICE_COLUMNS:
        actual = column_map.get(canonical)
        if actual is None:
            continue
        numeric = _to_numeric_series(data[actual])
        evaluable = numeric.notna()
        non_positive_mask = evaluable & (numeric <= 0)
        if non_positive_mask.any():
            affected_columns.append(canonical)
            affected_rows.extend(data.index[non_positive_mask].tolist())

    if not affected_columns:
        return Finding(rule_id="NON_POSITIVE_PRICES", status=ValidationStatus.PASS, message="All price values (Open, High, Low, Close) are positive.")

    unique_rows = _unique_ordered(affected_rows)
    return Finding(
        rule_id="NON_POSITIVE_PRICES",
        status=ValidationStatus.FAIL,
        message=f"Non-positive price value(s) found in column(s): {', '.join(affected_columns)}. {len(unique_rows)} row(s) affected.",
        affected_rows=tuple(unique_rows),
        metadata={"columns_with_non_positive": affected_columns},
    )


def _check_invalid_volume(data: pd.DataFrame, column_map: dict[str, str]) -> Finding:
    actual = column_map.get("Volume")
    if actual is None:
        return Finding(rule_id="INVALID_VOLUME", status=ValidationStatus.WARNING, message="Volume check skipped: Volume column not found.")

    numeric = _to_numeric_series(data[actual])
    evaluable = numeric.notna()

    negative_mask = evaluable & (numeric < 0)
    zero_mask = evaluable & (numeric == 0)

    if negative_mask.any():
        affected_rows = tuple(data.index[negative_mask].tolist())
        return Finding(
            rule_id="INVALID_VOLUME",
            status=ValidationStatus.FAIL,
            message=f"{len(affected_rows)} row(s) have negative volume. Volume must be zero or positive.",
            affected_rows=affected_rows,
        )

    if zero_mask.any():
        affected_rows = tuple(data.index[zero_mask].tolist())
        return Finding(
            rule_id="INVALID_VOLUME",
            status=ValidationStatus.WARNING,
            message=f"{len(affected_rows)} row(s) have zero volume. This may indicate a non-trading day, a data error, or a circuit-breaker halt.",
            affected_rows=affected_rows,
        )

    return Finding(rule_id="INVALID_VOLUME", status=ValidationStatus.PASS, message="All volume values are positive.")


def _check_trading_date_validity(data: pd.DataFrame, column_map: dict[str, str]) -> Finding:
    actual = column_map.get("Date")
    if actual is None:
        return Finding(rule_id="TRADING_DATE_VALIDITY", status=ValidationStatus.WARNING, message="Date validity check skipped: Date column not found.")

    date_col = data[actual]

    if pd.api.types.is_datetime64_any_dtype(date_col):
        return Finding(rule_id="TRADING_DATE_VALIDITY", status=ValidationStatus.PASS, message="Date column is already datetime-typed; all values are valid.")

    parsed = pd.to_datetime(date_col, errors="coerce")
    unparseable_mask = parsed.isna() & date_col.notna()

    if not unparseable_mask.any():
        return Finding(rule_id="TRADING_DATE_VALIDITY", status=ValidationStatus.PASS, message="All Date values can be parsed as valid dates.")

    affected_rows = tuple(data.index[unparseable_mask].tolist())
    bad_values = date_col[unparseable_mask].tolist()[:10]
    return Finding(
        rule_id="TRADING_DATE_VALIDITY",
        status=ValidationStatus.FAIL,
        message=f"{len(affected_rows)} row(s) contain Date values that cannot be parsed as dates.",
        affected_rows=affected_rows,
        metadata={"sample_bad_values": [str(v) for v in bad_values]},
    )


def _check_duplicate_dates(data: pd.DataFrame, column_map: dict[str, str]) -> Finding:
    actual = column_map.get("Date")
    if actual is None:
        return Finding(rule_id="DUPLICATE_DATES", status=ValidationStatus.WARNING, message="Duplicate date check skipped: Date column not found.")

    date_col = data[actual]
    parsed = pd.to_datetime(date_col, errors="coerce").dt.normalize()
    valid_mask = parsed.notna()
    parsed_valid = parsed[valid_mask]

    duplicate_date_mask_valid = parsed_valid.duplicated(keep=False)

    if not duplicate_date_mask_valid.any():
        return Finding(rule_id="DUPLICATE_DATES", status=ValidationStatus.PASS, message="No duplicate trading dates found.")

    dup_original_index = parsed_valid.index[duplicate_date_mask_valid]
    affected_rows = tuple(dup_original_index.tolist())
    dup_dates = parsed_valid[duplicate_date_mask_valid].drop_duplicates().dt.date.tolist()[:10]

    return Finding(
        rule_id="DUPLICATE_DATES",
        status=ValidationStatus.WARNING,
        message=f"{len(affected_rows)} row(s) share a trading date with at least one other row.",
        affected_rows=affected_rows,
        metadata={"sample_duplicate_dates": [str(d) for d in dup_dates]},
    )


def _to_numeric_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    return pd.to_numeric(series, errors="coerce")


def _unique_ordered(indices: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            result.append(idx)
    return result