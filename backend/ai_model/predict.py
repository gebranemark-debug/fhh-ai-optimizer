"""Inference layer for the FHH predictive-maintenance models.

Exposes the three functions the build guide specifies plus the 5-tier
recommendation mapping. The models are loaded lazily (and cached) so
importing this module is cheap.

    detect_anomaly(machine_id, recent_sensor_data=None)  -> 0..100
    predict_failure_probability(machine_id)              -> 0..1
    get_recommended_action(machine_id)                   -> dict {tier, action_text, score_percent}

Threshold mapping (locked, per fhh_backend_build_guide.pdf Prompt 3):

    >= 90%   CRITICAL   Stop line immediately. Replace component now.
    75-89%   HIGH       Schedule maintenance within 24 hours.
    50-74%   MEDIUM     Plan maintenance within 7 days.
    25-49%   LOW        Monitor closely. Increase inspection frequency.
    <  25%   NORMAL     Continue routine operations.

These thresholds match the API contract's risk-tier table in spirit but
follow the build guide's wording verbatim.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd


DEFAULT_ARTIFACT_DIR = Path("backend/ai_model/artifacts")
DEFAULT_FEATURES = Path("backend/timescale/features.parquet")


def _artifact_dir() -> Path:
    return Path(os.environ.get("FHH_AI_ARTIFACT_DIR", str(DEFAULT_ARTIFACT_DIR)))


def _features_path() -> Path:
    return Path(os.environ.get("FHH_AI_FEATURES", str(DEFAULT_FEATURES)))


# =============================================================================
# Model + feature cache
# =============================================================================

@dataclass
class _Bundle:
    rf: object                  # RandomForestClassifier
    iso: object                 # IsolationForest
    feature_columns: list[str]
    raw_min: float              # for anomaly-score normalization
    raw_max: float
    features_df: pd.DataFrame   # latest hourly features per machine_id


@lru_cache(maxsize=1)
def _load() -> _Bundle:
    art = _artifact_dir()
    rf_path = art / "failure_probability_rf.pkl"
    iso_path = art / "anomaly_isoforest.pkl"
    schema_path = art / "feature_schema.json"
    if not rf_path.exists() or not iso_path.exists():
        raise FileNotFoundError(
            f"Model artifacts not found in {art}. "
            f"Run `python backend/ai_model/train_model.py` first."
        )
    rf = joblib.load(rf_path)
    iso = joblib.load(iso_path)
    schema = json.loads(schema_path.read_text())

    fp = _features_path()
    if not fp.exists():
        raise FileNotFoundError(
            f"Features parquet not found at {fp}. "
            f"Run `python backend/timescale/etl.py --in-memory --out {fp}` first."
        )
    features = pd.read_parquet(fp)

    return _Bundle(
        rf=rf,
        iso=iso,
        feature_columns=schema["feature_columns"],
        raw_min=float(schema["anomaly_score_normalization"]["raw_min"]),
        raw_max=float(schema["anomaly_score_normalization"]["raw_max"]),
        features_df=features,
    )


def reset_cache() -> None:
    """For tests — drop the cached models so the next call reloads them."""
    _load.cache_clear()


# =============================================================================
# Helpers
# =============================================================================

def _rows_for_machine(b: _Bundle, machine_id: str) -> pd.DataFrame:
    """All fully-populated feature rows for a machine, sorted ascending."""
    df = b.features_df
    sub = df[df["machine_id"] == machine_id]
    if sub.empty:
        raise KeyError(f"machine_id {machine_id!r} not in features dataset")
    feat = sub[b.feature_columns].apply(pd.to_numeric, errors="coerce")
    sub = sub[feat.notna().all(axis=1)]
    if sub.empty:
        raise KeyError(f"machine_id {machine_id!r} has no fully-populated feature rows")
    return sub.sort_values("hour_bucket")


def _latest_row_for_machine(b: _Bundle, machine_id: str) -> pd.Series:
    """Most recent hourly feature row for a machine, fully populated."""
    return _rows_for_machine(b, machine_id).iloc[-1]


# Demo-friendly default window. The seeded dataset's last labeled failure
# is at 2026-04-03 and the anchor "today" is 2026-04-25, so a 30-day window
# captures the peak risk for at least three of the four machines. In a
# live deployment with new sensor data flowing in, this becomes the
# "rolling 30-day peak" — still a sensible UX.
DEFAULT_PEAK_WINDOW_DAYS = 30


def _row_to_X(b: _Bundle, row: pd.Series) -> pd.DataFrame:
    """Return a 1-row DataFrame in the exact column order the model expects."""
    return pd.DataFrame([[float(row[c]) for c in b.feature_columns]],
                        columns=b.feature_columns)


def _normalize_anomaly(b: _Bundle, raw: np.ndarray) -> np.ndarray:
    """Map raw anomaly score (higher = more anomalous) to a 0-100 scale using
    the min/max captured at training time. Clamped to [0, 100]."""
    span = max(b.raw_max - b.raw_min, 1e-12)
    pct = (raw - b.raw_min) / span * 100.0
    return np.clip(pct, 0.0, 100.0)


# =============================================================================
# Public API
# =============================================================================

def detect_anomaly(
    machine_id: str,
    recent_sensor_data: Optional[pd.DataFrame] = None,
) -> float:
    """Return a 0-100 anomaly score for the given machine.

    ``recent_sensor_data``, if provided, must be a single-row DataFrame
    containing the same feature columns the model was trained on. If
    omitted, the most recent hourly feature row from features.parquet is
    used."""
    b = _load()
    if recent_sensor_data is not None:
        missing = [c for c in b.feature_columns if c not in recent_sensor_data.columns]
        if missing:
            raise ValueError(f"recent_sensor_data missing columns: {missing}")
        X = recent_sensor_data[b.feature_columns].astype(float)
    else:
        X = _row_to_X(b, _latest_row_for_machine(b, machine_id))

    raw = -b.iso.decision_function(X)        # bigger = more anomalous
    score = float(_normalize_anomaly(b, raw)[0])
    return round(score, 2)


def predict_failure_probability(
    machine_id: str,
    window_days: int = DEFAULT_PEAK_WINDOW_DAYS,
    mode: str = "peak",
) -> float:
    """Return a continuous probability in [0.0, 1.0] that ``machine_id`` will
    experience a failure within the next 72 hours.

    ``mode``:
      - ``"peak"`` (default) — returns the maximum probability the model
        observed across the last ``window_days`` of feature rows. This is
        what the dashboard surfaces, so a machine that was trending toward
        a labeled failure earlier in the window stays visible until the
        window passes.
      - ``"current"`` — returns the probability for the latest hour
        only. Useful for production-style "what's the state right now"
        queries.
    """
    b = _load()
    rows = _rows_for_machine(b, machine_id)

    if mode == "current":
        X = _row_to_X(b, rows.iloc[-1])
        return round(float(b.rf.predict_proba(X)[0, 1]), 4)

    if mode != "peak":
        raise ValueError(f"unknown mode {mode!r}; expected 'peak' or 'current'")

    # Peak over the last `window_days`.
    cutoff = rows["hour_bucket"].max() - pd.Timedelta(days=window_days)
    window = rows[rows["hour_bucket"] >= cutoff]
    if window.empty:
        window = rows.tail(1)
    X = window[b.feature_columns].astype(float)
    probs = b.rf.predict_proba(X)[:, 1]
    return round(float(probs.max()), 4)


# Threshold mapping (build guide v1.1, Prompt 3 — locked).
_TIERS = (
    (0.90, "critical", "CRITICAL: Stop line immediately. Replace component now."),
    (0.75, "high",     "HIGH: Schedule maintenance within 24 hours."),
    (0.50, "medium",   "MEDIUM: Plan maintenance within 7 days."),
    (0.25, "low",      "LOW: Monitor closely. Increase inspection frequency."),
    (0.00, "normal",   "NORMAL: Continue routine operations."),
)


def threshold_to_tier(probability: float) -> tuple[str, str]:
    """Map a 0-1 probability to (tier_name, action_text) using the build
    guide's locked thresholds. ``probability`` may be slightly outside
    [0,1]; it's clamped first."""
    p = max(0.0, min(1.0, float(probability)))
    for cutoff, tier, text in _TIERS:
        if p >= cutoff:
            return tier, text
    # unreachable — final tier is the >= 0.0 catch-all.
    return _TIERS[-1][1], _TIERS[-1][2]


def get_recommended_action(machine_id: str) -> dict:
    """Return the recommended action for a machine based on its current
    failure probability. Output shape:

        {
            "machine_id": "al-nakheel",
            "failure_probability": 0.87,         # 0-1 continuous
            "score_percent": 87.0,               # convenience for the UI
            "tier": "high",                      # one of normal|low|medium|high|critical
            "action_text": "HIGH: Schedule maintenance within 24 hours.",
        }
    """
    proba = predict_failure_probability(machine_id)
    tier, text = threshold_to_tier(proba)
    return {
        "machine_id": machine_id,
        "failure_probability": proba,
        "score_percent": round(proba * 100.0, 2),
        "tier": tier,
        "action_text": text,
    }


# Maps the predict.py 5-tier scale to the API contract's 4-tier risk_tier
# enum. The contract has no "high" tier — anything >= 75% is "critical" for
# UI badge color purposes; "low" maps to the contract's "watch" tier.
_TIER_TO_API_RISK = {
    "critical": "critical",
    "high":     "critical",
    "medium":   "warning",
    "low":      "watch",
    "normal":   "healthy",
}


def tier_to_api_risk_tier(tier: str) -> str:
    return _TIER_TO_API_RISK.get(tier, "healthy")


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Quick CLI smoke test for the inference layer.")
    p.add_argument("machine_id", nargs="?", default="al-nakheel",
                   help="Machine ID to score (default: al-nakheel).")
    args = p.parse_args()

    anomaly = detect_anomaly(args.machine_id)
    proba = predict_failure_probability(args.machine_id)
    rec = get_recommended_action(args.machine_id)

    print(f"machine_id              {args.machine_id}")
    print(f"anomaly_score (0-100)   {anomaly}")
    print(f"failure_probability     {proba}  ({proba*100:.2f}%)")
    print(f"tier                    {rec['tier']}")
    print(f"action                  {rec['action_text']}")
    print(f"api_risk_tier           {tier_to_api_risk_tier(rec['tier'])}")


if __name__ == "__main__":
    main()
