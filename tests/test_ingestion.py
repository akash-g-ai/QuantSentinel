"""Tests for CSV ingestion."""

from pathlib import Path

import pandas as pd
import pytest

from quantsentinel.ingestion import (
    EmptyDatasetError,
    UnreadableDatasetError,
    UnsupportedFileTypeError,
    load_csv,
)


def test_load_csv_returns_dataframe_without_changing_values(tmp_path: Path) -> None:
    source = tmp_path / "prices.csv"
    original = (
        "date,close\n"
        "2024-01-02,100\n"
        "2024-01-02,100\n"
        "2024-01-03,\n"
    )
    source.write_text(original, encoding="utf-8")
    before = _snapshot(source)

    frame = load_csv(str(source))

    assert isinstance(frame, pd.DataFrame)
    assert list(frame.columns) == ["date", "close"]
    assert len(frame) == 3
    assert frame.loc[0, "close"] == 100
    assert frame.loc[1, "close"] == 100
    assert pd.isna(frame.loc[2, "close"])
    assert _snapshot(source) == before


def test_load_csv_accepts_path_object(tmp_path: Path) -> None:
    source = tmp_path / "OHLC.CSV"
    source.write_text("symbol\nNIFTY\n", encoding="utf-8")
    before = _snapshot(source)

    frame = load_csv(source)

    assert list(frame["symbol"]) == ["NIFTY"]
    assert _snapshot(source) == before


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError, match="CSV file not found"):
        load_csv(missing)

    assert not missing.exists()


def test_unsupported_extension_raises_and_leaves_file_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "prices.xlsx"
    source.write_text("date,close\n2024-01-02,100\n", encoding="utf-8")
    before = _snapshot(source)

    with pytest.raises(UnsupportedFileTypeError, match="Unsupported file extension"):
        load_csv(source)

    assert _snapshot(source) == before


def test_empty_file_raises_and_leaves_file_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "empty.csv"
    source.write_bytes(b"")
    before = _snapshot(source)

    with pytest.raises(EmptyDatasetError, match="CSV file is empty"):
        load_csv(source)

    assert _snapshot(source) == before


def test_invalid_utf8_raises_and_leaves_file_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "encoded.csv"
    source.write_bytes(b"date,close\n\xff\xfe\n")
    before = _snapshot(source)

    with pytest.raises(UnreadableDatasetError, match="not valid UTF-8"):
        load_csv(source)

    assert _snapshot(source) == before


def test_malformed_csv_raises_and_leaves_file_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "broken.csv"
    source.write_text('date,close\n"unterminated,100\n', encoding="utf-8")
    before = _snapshot(source)

    with pytest.raises(UnreadableDatasetError, match="could not be parsed"):
        load_csv(source)

    assert _snapshot(source) == before


def test_path_must_be_string_or_path() -> None:
    with pytest.raises(TypeError, match="string or pathlib.Path"):
        load_csv(123)  # type: ignore[arg-type]


def _snapshot(path: Path) -> tuple[bytes, int]:
    stat = path.stat()
    return path.read_bytes(), stat.st_mtime_ns
