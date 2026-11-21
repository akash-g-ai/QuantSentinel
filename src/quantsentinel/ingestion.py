"""Data ingestion.

Loads an uploaded financial dataset and hands it to the pipeline. The file
under data/raw is read-only. Ingestion must not delete, overwrite, or edit
the original records.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError


class IngestionError(Exception):
    """Base error for dataset ingestion failures."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when the file extension is not .csv."""


class EmptyDatasetError(IngestionError):
    """Raised when a CSV file has no parseable content."""


class UnreadableDatasetError(IngestionError):
    """Raised when a file cannot be decoded or parsed as CSV."""


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a CSV file into a DataFrame without modifying the source file.

    The file is opened for reading only. Rows are not dropped, duplicates are
    not removed, and missing values are not filled. Structural, financial, and
    statistical checks belong in later pipeline stages.

    Args:
        path: Location of an existing ``.csv`` file.

    Returns:
        The CSV contents as a DataFrame. Pandas may represent empty fields as
        missing values; the source file is left unchanged.

    Raises:
        TypeError: ``path`` is not a string or :class:`pathlib.Path`.
        FileNotFoundError: ``path`` does not exist.
        UnsupportedFileTypeError: The file suffix is not ``.csv``.
        PermissionError: The file cannot be opened for reading.
        EmptyDatasetError: The file is empty or has no parseable CSV content.
        UnreadableDatasetError: The file is not a readable file, is not valid
            UTF-8, or cannot be parsed as CSV.
    """
    source = _require_csv_file(path)
    try:
        return pd.read_csv(source, encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(f"Cannot read CSV file: {source}") from exc
    except UnicodeDecodeError as exc:
        raise UnreadableDatasetError(
            f"CSV file is not valid UTF-8: {source}"
        ) from exc
    except EmptyDataError as exc:
        raise EmptyDatasetError(f"CSV file is empty: {source}") from exc
    except ParserError as exc:
        raise UnreadableDatasetError(
            f"CSV file could not be parsed: {source}"
        ) from exc


def _require_csv_file(path: str | Path) -> Path:
    """Return a readable CSV path, or raise a specific ingestion error."""
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or pathlib.Path")

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"CSV file not found: {source}")
    if not source.is_file():
        raise UnreadableDatasetError(f"CSV path is not a file: {source}")
    if source.suffix.lower() != ".csv":
        raise UnsupportedFileTypeError(
            f"Unsupported file extension {source.suffix!r}: {source}. Expected .csv."
        )
    if source.stat().st_size == 0:
        raise EmptyDatasetError(f"CSV file is empty: {source}")
    return source
