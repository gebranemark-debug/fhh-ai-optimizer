"""Train the FHH predictive-maintenance models from the ETL feature dataset.

Two models are trained from the same feature matrix and saved as joblib
.pkl files:

1. Isolation Forest (unsupervised) — used by ``predict.detect_anomaly`` to
   score "how unusual is the current sensor pattern?" on a 0-100 scale.
2. RandomForestClassifier (supervised) — trained against the
   ``target_failure_within_72h`` label produced by the ETL.
   ``predict_proba`` gives a CONTINUOUS PROBABILITY (0-1) that the model
   surfaces in the API as 0-100. This is the regressor-style output the
   build guide specifies — a binary classifier under the hood, but the
   exposed value is a continuous probability, never a yes/no label.

Run:
    python backend/ai_model/train_model.py
    python backend/ai_model/train_model.py --features path/to/features.parquet
    python backend/ai_model/train_model.py --out backend/ai_model/artifacts
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    average_precision_score, classification_report, roc_auc_score,
)
from sklearn.model_selection import train_test_split


# Defaults wire to the layer that produced features.parquet.
DEFAULT_FEATURES = Path("backend/timescale/features.parquet")
DEFAULT_OUT_DIR = Path("backend/ai_model/artifacts")

# Columns we never feed the model — IDs, time keys, the label itself.
NON_FEATURE_COLS = ("machine_id", "hour_bucket", "target_failure_within_72h")

# Anomaly-detection contamination prior. The simulator's failure overlays
# touch ~1-2% of rows, so 0.02 is a defensible choice.
ANOMALY_CONTAMINATION = 0.02

# Random Forest hyperparameters — class_weight='balanced' is critical
# because target_failure_within_72h is rare (~1% positive rate).
RF_PARAMS = dict(
    n_estimators=300,
    max_depth=None,
    min_samples_leaf=5,
    class_weight="balanced",
    n_jobs=-1,
    random_state=42,
)
ISO_PARAMS = dict(
    n_estimators=200,
    contamination=ANOMALY_CONTAMINATION,
    random_state=42,
    n_jobs=-1,
)


def _select_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Drop ID/label columns, keep numeric features, drop rows where any
    feature is NaN (the rolling 7-day vibration slope is NaN for the first
    ~12 hours of each machine)."""
    feature_cols = [c for c in df.columns if c not in NON_FEATURE_COLS]
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    y = df["target_failure_within_72h"].astype(int)

    # Drop rows where any feature is NaN; the model can't accept missing values.
    mask = X.notna().all(axis=1) & y.notna()
    return X[mask].reset_index(drop=True), y[mask].reset_index(drop=True), feature_cols


def train(features_path: Path, out_dir: Path) -> dict:
    """Train both models and save artifacts. Returns metrics for logging."""
    if not features_path.exists():
        raise FileNotFoundError(
            f"features file not found at {features_path!s}. "
            f"Run `python backend/timescale/etl.py --in-memory --out {features_path}` first."
        )

    print(f"[train] loading {features_path}")
    df = pd.read_parquet(features_path)
    print(f"[train] feature dataset: {len(df):,} rows × {df.shape[1]} columns")

    X, y, feature_cols = _select_features(df)
    print(f"[train] usable rows after NaN drop: {len(X):,}")
    print(f"[train] class balance: positive={int(y.sum())}, negative={int((~y.astype(bool)).sum())}, "
          f"positive_rate={y.mean():.4%}")

    if y.sum() == 0:
        raise SystemExit("[train] FAILED: no positive examples in target — ETL didn't label any window.")

    # ---- supervised: failure-probability classifier --------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )
    print(f"[train] training RandomForestClassifier on {len(X_train):,} rows ...")
    rf = RandomForestClassifier(**RF_PARAMS)
    rf.fit(X_train, y_train)

    proba_test = rf.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, proba_test))
    ap = float(average_precision_score(y_test, proba_test))
    pred_at_05 = (proba_test >= 0.5).astype(int)
    print(f"[train]   ROC-AUC      = {auc:.4f}")
    print(f"[train]   PR-AUC       = {ap:.4f}")
    print("[train]   classification_report @ threshold 0.5:")
    print(classification_report(y_test, pred_at_05, digits=4, zero_division=0))

    # ---- unsupervised: anomaly detector --------------------------------------
    print(f"[train] training IsolationForest on {len(X):,} rows (full dataset, unsupervised) ...")
    iso = IsolationForest(**ISO_PARAMS)
    iso.fit(X)

    # Quick sanity: anomaly score should be higher (more anomalous) on the
    # positive-labeled rows than on the rest, on average.
    raw = -iso.decision_function(X)            # bigger = more anomalous
    anomaly_score = (raw - raw.min()) / (raw.max() - raw.min() + 1e-12) * 100.0
    sep = float(anomaly_score[y == 1].mean() - anomaly_score[y == 0].mean())
    print(f"[train]   mean anomaly_score(pos) - mean anomaly_score(neg) = {sep:.2f}")

    # ---- persist -------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    rf_path = out_dir / "failure_probability_rf.pkl"
    iso_path = out_dir / "anomaly_isoforest.pkl"
    schema_path = out_dir / "feature_schema.json"
    metrics_path = out_dir / "metrics.json"

    joblib.dump(rf, rf_path)
    joblib.dump(iso, iso_path)
    schema_path.write_text(json.dumps({
        "feature_columns": feature_cols,
        "non_feature_columns": list(NON_FEATURE_COLS),
        "anomaly_score_normalization": {
            "method": "min-max over training set",
            "raw_min": float(raw.min()),
            "raw_max": float(raw.max()),
        },
    }, indent=2))

    metrics = {
        "rows_total": int(len(df)),
        "rows_usable": int(len(X)),
        "positive_rate": float(y.mean()),
        "rf_roc_auc": auc,
        "rf_pr_auc": ap,
        "anomaly_score_separation": sep,
        "feature_count": len(feature_cols),
    }
    metrics_path.write_text(json.dumps(metrics, indent=2))

    print(f"[train] saved RandomForestClassifier  → {rf_path}")
    print(f"[train] saved IsolationForest         → {iso_path}")
    print(f"[train] saved feature schema          → {schema_path}")
    print(f"[train] saved metrics                 → {metrics_path}")
    print("[train] OK.")
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description="Train FHH predictive-maintenance models.")
    p.add_argument("--features", type=Path, default=DEFAULT_FEATURES,
                   help=f"Path to the ETL feature parquet (default {DEFAULT_FEATURES}).")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR,
                   help=f"Directory to write .pkl + metrics.json (default {DEFAULT_OUT_DIR}).")
    args = p.parse_args()
    train(args.features, args.out)


if __name__ == "__main__":
    main()
