"""Time-series-aware evaluation of the FHH predictive-maintenance model.

Reads the same features.parquet the train script trains on, applies a
**chronological** 80/20 split (train on the first 80% of hours, test on
the last 20%), and reports metrics for the failure class:

  - Precision, Recall, F1 (at threshold 0.5)
  - ROC-AUC (ranking quality, threshold-independent)
  - Confusion matrix (TP, FP, TN, FN)
  - Class distribution (positives in train vs test)

Why time-based, not random: a random split leaks information across the
72-hour failure horizon. A row labelled positive at hour T is a leading
indicator of a failure at T+72h, and rows around that failure event are
correlated. Random k-fold puts neighbouring hours in different folds and
the model effectively memorises local context. A time-based holdout
mirrors how the model is actually used in production — predict the
future from the past.

Run:
    python backend/ai_model/evaluate_model.py
    python backend/ai_model/evaluate_model.py --features path/to/features.parquet
    python backend/ai_model/evaluate_model.py --out path/to/report.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


_HERE = Path(__file__).parent
DEFAULT_FEATURES = Path("backend/timescale/features.parquet")
DEFAULT_ARTIFACTS = _HERE / "artifacts"
DEFAULT_REPORT = _HERE / "evaluation_report.md"

# Same list as train_model.py — keep in sync. ID columns + label.
NON_FEATURE_COLS = ("machine_id", "hour_bucket", "target_failure_within_72h")

# Default classification threshold. 0.5 is the sklearn default; in real
# operations you'd tune this on a validation set against the cost of a
# missed failure ($20K/hr downtime) vs. a false alarm ($5K inspection).
THRESHOLD = 0.5


def _select_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    feature_cols = [c for c in df.columns if c not in NON_FEATURE_COLS]
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    y = df["target_failure_within_72h"].astype(int)
    mask = X.notna().all(axis=1) & y.notna()
    return X[mask].reset_index(drop=True), y[mask].reset_index(drop=True), feature_cols


def time_based_split(
    df: pd.DataFrame,
    test_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sort by hour_bucket, take the last ``test_fraction`` as the test
    set. Returns (train_df, test_df) — same columns as ``df``."""
    df = df.sort_values("hour_bucket").reset_index(drop=True)
    cutoff = int(len(df) * (1.0 - test_fraction))
    return df.iloc[:cutoff].copy(), df.iloc[cutoff:].copy()


def evaluate(
    features_path: Path = DEFAULT_FEATURES,
    artifacts_dir: Path = DEFAULT_ARTIFACTS,
    report_path: Path = DEFAULT_REPORT,
    threshold: float = THRESHOLD,
) -> dict:
    print(f"[eval] loading features: {features_path}")
    df = pd.read_parquet(features_path)
    print(f"[eval] feature dataset: {len(df):,} rows × {df.shape[1]} cols")

    print("[eval] time-based 80/20 split (train = first 80% by hour_bucket)")
    train_df, test_df = time_based_split(df, test_fraction=0.2)
    print(f"[eval] train range: {train_df['hour_bucket'].min()} .. {train_df['hour_bucket'].max()}")
    print(f"[eval] test  range: {test_df['hour_bucket'].min()} .. {test_df['hour_bucket'].max()}")

    X_train, y_train, _ = _select_features(train_df)
    X_test,  y_test,  feat_cols = _select_features(test_df)

    train_pos = int(y_train.sum())
    test_pos = int(y_test.sum())
    print(f"[eval] usable train rows: {len(X_train):,}  ({train_pos:,} positive)")
    print(f"[eval] usable test  rows: {len(X_test):,}  ({test_pos:,} positive)")

    if test_pos == 0:
        raise SystemExit("[eval] FAILED: test set has zero positive labels — "
                         "insufficient signal in last 20% of timeline.")

    rf_path = artifacts_dir / "failure_probability_rf.pkl"
    schema_path = artifacts_dir / "feature_schema.json"
    if not rf_path.exists():
        raise SystemExit(
            f"[eval] FAILED: RF model not found at {rf_path}. "
            f"Run `python backend/ai_model/train_model.py` first."
        )
    print(f"[eval] loading RF model: {rf_path}")
    rf = joblib.load(rf_path)

    # Re-order test features to match the schema the model was trained on,
    # in case column order shifted in a future ETL change.
    if schema_path.exists():
        schema = json.loads(schema_path.read_text())
        ordered_cols = schema["feature_columns"]
        missing = [c for c in ordered_cols if c not in X_test.columns]
        if missing:
            raise SystemExit(f"[eval] FAILED: features.parquet missing trained columns: {missing}")
        X_test_ordered = X_test[ordered_cols]
    else:
        X_test_ordered = X_test

    print(f"[eval] running predictions on {len(X_test_ordered):,} test rows")
    proba = rf.predict_proba(X_test_ordered)[:, 1]
    pred = (proba >= threshold).astype(int)

    # Metrics for the positive (failure) class.
    precision = float(precision_score(y_test, pred, zero_division=0))
    recall    = float(recall_score(y_test, pred, zero_division=0))
    f1        = float(f1_score(y_test, pred, zero_division=0))
    auc       = float(roc_auc_score(y_test, proba)) if y_test.nunique() > 1 else float("nan")

    cm = confusion_matrix(y_test, pred, labels=[0, 1])
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

    metrics = {
        "n_train": int(len(X_train)),
        "n_test":  int(len(X_test)),
        "positives_train": train_pos,
        "positives_test":  test_pos,
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test":  float(y_test.mean()),
        "threshold": float(threshold),
        "precision": precision,
        "recall":    recall,
        "f1":        f1,
        "roc_auc":   auc,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "train_range": [str(train_df["hour_bucket"].min()), str(train_df["hour_bucket"].max())],
        "test_range":  [str(test_df["hour_bucket"].min()),  str(test_df["hour_bucket"].max())],
    }

    print()
    print(f"[eval] precision @ {threshold:.2f}: {precision:.4f}")
    print(f"[eval] recall    @ {threshold:.2f}: {recall:.4f}")
    print(f"[eval] f1        @ {threshold:.2f}: {f1:.4f}")
    print(f"[eval] roc-auc            : {auc:.4f}")
    print(f"[eval] confusion matrix   : tp={tp}  fp={fp}  tn={tn}  fn={fn}")

    _write_markdown(metrics, report_path)
    print(f"[eval] wrote {report_path}")
    return metrics


def _write_markdown(m: dict, path: Path) -> None:
    """Render a self-contained evaluation report. Includes the metrics
    table, the confusion matrix, the train/test split details, and a
    one-paragraph interpretation that calls out where these numbers
    sit relative to the production thresholds called out in the spec."""
    p = m["precision"]
    r = m["recall"]
    f1 = m["f1"]
    auc = m["roc_auc"]
    cm = m["confusion_matrix"]

    # Production thresholds from the spec brief.
    target_recall = 0.85
    target_precision = 0.70
    recall_ok = "✅ meets" if r >= target_recall else "❌ below"
    precision_ok = "✅ meets" if p >= target_precision else "❌ below"

    interpretation = _interpret(p, r, f1, auc, recall_ok, precision_ok)

    md = f"""# FHH Predictive-Maintenance Model Evaluation

Time-based 80/20 holdout on `backend/timescale/features.parquet`. The
training set covers the **first 80% of hours**; the test set is the
**last 20%**. This avoids the leakage a random split would introduce
across the 72-hour failure horizon.

## Split

| | Hours | Failure positives | Positive rate |
|---|---|---|---|
| **Train** | {m['n_train']:,} | {m['positives_train']:,} | {m['positive_rate_train']:.2%} |
| **Test**  | {m['n_test']:,}  | {m['positives_test']:,}  | {m['positive_rate_test']:.2%} |

- Train range: `{m['train_range'][0]}` → `{m['train_range'][1]}`
- Test range:  `{m['test_range'][0]}` → `{m['test_range'][1]}`

## Metrics for the failure class (label = 1)

Threshold = **{m['threshold']:.2f}** (sklearn default; tunable on the
cost ratio between a missed failure and a false alarm).

| Metric | Value | Production target | Status |
|---|---|---|---|
| **Precision** | **{p:.4f}** | ≥ 0.70 | {precision_ok} |
| **Recall**    | **{r:.4f}** | ≥ 0.85 | {recall_ok} |
| **F1**        | **{f1:.4f}** | — | — |
| **ROC-AUC**   | **{auc:.4f}** | — | — |

## Confusion matrix

|                    | Predicted negative | Predicted positive |
|--------------------|--------------------|---------------------|
| **Actual negative** | TN = {cm['tn']:,} | FP = {cm['fp']:,} |
| **Actual positive** | FN = {cm['fn']:,} | TP = {cm['tp']:,} |

## Interpretation

{interpretation}

---
*Generated by `python backend/ai_model/evaluate_model.py` against the
RandomForestClassifier in `backend/ai_model/artifacts/`. Re-run after
every retrain.*
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md)


def _interpret(
    precision: float,
    recall: float,
    f1: float,
    auc: float,
    recall_status: str,
    precision_status: str,
) -> str:
    parts: list[str] = []

    parts.append(
        f"Recall is **{recall:.3f}** — {recall_status} the 0.85 target. "
        f"In production terms, that means the model would catch "
        f"{recall:.0%} of failures within their 72-hour warning window. "
        f"Each missed failure is worth ~$20K/hour of unplanned downtime, "
        f"so recall is the metric that matters most for predictive "
        f"maintenance."
    )
    parts.append(
        f"Precision is **{precision:.3f}** — {precision_status} the 0.70 "
        f"target. At this precision, roughly {(1.0 - precision) * 100:.0f}% "
        f"of flagged hours would be false alarms; each one costs ~$5K "
        f"in inspection time, so the ratio of recall (catches) to "
        f"precision (false alarms) directly determines whether the "
        f"system saves more than it costs."
    )
    parts.append(
        f"ROC-AUC of **{auc:.3f}** measures threshold-independent "
        f"ranking quality. Above 0.90 is strong; in the 0.80-0.90 band "
        f"there's still room to tune the threshold against the cost "
        f"ratio above. F1 sits at {f1:.3f}."
    )
    parts.append(
        "**Caveat — synthetic data sets an upper bound on these "
        "numbers.** The training set was generated by a deterministic "
        "simulator with explicit failure precursor patterns; real "
        "Valmet failure data would be noisier and more varied, with "
        "edge cases the simulator doesn't represent. Expect the "
        "production numbers to land below these — possibly "
        "substantially below — until the model is retrained on real "
        "DCS history and labelled events."
    )
    return "\n\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    p.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    p.add_argument("--out", type=Path, default=DEFAULT_REPORT,
                   help=f"Where to write the markdown report (default {DEFAULT_REPORT}).")
    p.add_argument("--threshold", type=float, default=THRESHOLD)
    args = p.parse_args()
    evaluate(
        features_path=args.features,
        artifacts_dir=args.artifacts,
        report_path=args.out,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
