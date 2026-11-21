"""QuantSentinel - ECOD-based anomaly detection module.

This module provides lightweight ML-based anomaly detection using PyOD's
ECOD (Empirical Cumulative Distribution Functions) algorithm.

Anomalies detected:
- Price anomalies (unusual OHLC patterns)
- Volume anomalies (unusual trading volume spikes)
- Return anomalies (unusual price changes)

Usage:
    from quantsentinel.anomaly import detect_anomalies

    df = load_your_data()
    anomalies = detect_anomalies(df)

Note:
    ECOD is a lightweight, unsupervised anomaly detector suitable for
    financial time series. It does not require training data or pretrained
    weights. It fits on the supplied dataset and generates anomaly scores.

    Anomalies are reported separately from structural, financial, and
    statistical validation findings. They are NOT trading signals.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from pyod.models.ecod import ECOD

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)


def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare numerical features for ECOD from OHLCV data.

    Features:
    - daily_return: Percentage change in close price
    - price_range: High - Low
    - volume_log: Log of volume (to handle large values)
    - price_volatility: Standard deviation of returns (rolling)

    Args:
        df: DataFrame with columns Date, Open, High, Low, Close, Volume

    Returns:
        DataFrame with prepared numerical features
    """
    features = pd.DataFrame(index=df.index)

    # Daily return
    features['daily_return'] = df['Close'].pct_change()

    # Price range ( High - Low )
    features['price_range'] = df['High'] - df['Low']

    # Log volume (handle zero by adding small epsilon)
    epsilon = 1e-6
    features['volume_log'] = np.log(df['Volume'] + epsilon)

    # Price volatility (rolling standard deviation of returns)
    features['price_volatility'] = features['daily_return'].rolling(window=5, min_periods=1).std()

    # Replace infinity with NaN
    features = features.replace([np.inf, -np.inf], np.nan)

    # Fill NaN values with column means
    features = features.fillna(features.mean())

    return features


def detect_anomalies(df: pd.DataFrame, contamination: float = 0.1) -> dict[str, Any]:
    """Detect anomalies using ECOD algorithm.

    Args:
        df: DataFrame with columns Date, Open, High, Low, Close, Volume
        contamination: Expected proportion of outliers in dataset (0-1)

    Returns:
        Dictionary with:
        - anomaly_labels: Array of 0 (normal) or 1 (anomaly)
        - anomaly_scores: Array of anomaly scores (higher = more anomalous)
        - detected_rows: List of row indices with anomalies
        - feature_stats: Dictionary with feature statistics
        - notes: List of informational notes
    """
    notes = []

    # Validate required columns
    required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        return {
            'anomaly_labels': np.array([]),
            'anomaly_scores': np.array([]),
            'detected_rows': [],
            'feature_stats': {},
            'notes': [f"Missing required columns: {missing_columns}"] + notes,
        }

    # Check for sufficient data
    if len(df) < 10:
        notes.append(f"Dataset has only {len(df)} records. ECOD works best with 10+ records.")
        return {
            'anomaly_labels': np.zeros(len(df), dtype=int),
            'anomaly_scores': np.zeros(len(df)),
            'detected_rows': [],
            'feature_stats': {},
            'notes': notes,
        }

    # Prepare features
    try:
        features = _prepare_features(df)
    except Exception as exc:
        notes.append(f"Feature preparation failed: {str(exc)}")
        return {
            'anomaly_labels': np.zeros(len(df), dtype=int),
            'anomaly_scores': np.zeros(len(df)),
            'detected_rows': [],
            'feature_stats': {},
            'notes': notes,
        }

    # Check for valid feature data
    if features.isnull().all().all():
        notes.append("All feature values are invalid. Cannot run ECOD.")
        return {
            'anomaly_labels': np.zeros(len(df), dtype=int),
            'anomaly_scores': np.zeros(len(df)),
            'detected_rows': [],
            'feature_stats': {},
            'notes': notes,
        }

    # Fit ECOD and predict
    try:
        ecod = ECOD(contamination=contamination)
        ecod.fit(features.values)

        anomaly_labels = ecod.labels_
        anomaly_scores = ecod.decision_scores_

        # Get anomaly row indices (0-indexed)
        detected_rows = [int(i) for i in np.where(anomaly_labels == 1)[0]]

        # Feature statistics for reporting
        feature_stats = {
            'n_records': len(df),
            'n_features': features.shape[1],
            'n_anomalies': int(sum(anomaly_labels)),
            'contamination': contamination,
            'features': list(features.columns),
            'mean_daily_return': float(features['daily_return'].mean()),
            'std_daily_return': float(features['daily_return'].std()),
            'mean_volume_log': float(features['volume_log'].mean()),
        }

        notes.append("ECOD anomaly detection completed successfully.")

        return {
            'anomaly_labels': anomaly_labels.tolist(),
            'anomaly_scores': anomaly_scores.tolist(),
            'detected_rows': detected_rows,
            'feature_stats': feature_stats,
            'notes': notes,
        }

    except Exception as exc:
        notes.append(f"ECOD inference failed: {str(exc)}")
        return {
            'anomaly_labels': np.zeros(len(df), dtype=int),
            'anomaly_scores': np.zeros(len(df)),
            'detected_rows': [],
            'feature_stats': {},
            'notes': notes,
        }
