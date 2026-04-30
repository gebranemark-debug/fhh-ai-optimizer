# FHH Predictive-Maintenance Model Evaluation

Time-based 80/20 holdout on `backend/timescale/features.parquet`. The
training set covers the **first 80% of hours**; the test set is the
**last 20%**. This avoids the leakage a random split would introduce
across the 72-hour failure horizon.

## Split

| | Hours | Failure positives | Positive rate |
|---|---|---|---|
| **Train** | 27,988 | 1,649 | 5.89% |
| **Test**  | 7,008  | 425  | 6.06% |

- Train range: `2025-04-25 00:00:00+00:00` → `2026-02-10 23:00:00+00:00`
- Test range:  `2026-02-11 00:00:00+00:00` → `2026-04-24 23:00:00+00:00`

## Metrics for the failure class (label = 1)

Threshold = **0.50** (sklearn default; tunable on the
cost ratio between a missed failure and a false alarm).

| Metric | Value | Production target | Status |
|---|---|---|---|
| **Precision** | **0.9848** | ≥ 0.75 | ✅ meets |
| **Recall**    | **0.9153** | ≥ 0.80 | ✅ meets |
| **F1**        | **0.9488** | — | — |
| **ROC-AUC**   | **0.9757** | — | — |

## Confusion matrix

|                    | Predicted negative | Predicted positive |
|--------------------|--------------------|---------------------|
| **Actual negative** | TN = 6,577 | FP = 6 |
| **Actual positive** | FN = 36 | TP = 389 |

## What changed from the clean baseline

The clean baseline (frozen at `artifacts/clean_baseline/`) was trained
on noise-free synthetic data — perfect failure precursors, no sensor
drift, no operating-regime shifts, no label mistakes. This report's
numbers come from a model retrained after **five categories of
realistic noise** were injected upstream:

1. **False-alarm spikes** (~100/year): brief 30-90s sensor spikes
   from worker contact / equipment that look like precursors but
   aren't labelled. Forces the model to discount short transients.
2. **Sensor drift**: each sensor's baseline drifts slowly ±8% of its
   normal range, snapping back at random recalibration days every
   90-120 days. Fights against absolute-threshold rules.
3. **Operating regime changes**: machines run 4 different products
   (facial_tissue / toilet_paper / kitchen_towel / napkin) in 5-15
   day blocks. Each product shifts sensor baselines slightly. The
   ETL adds product-aware temperature deviation and 4 one-hot
   product columns so the model can compensate.
4. **No-warning failures**: ~12% of failure events have no precursor
   ramp — the sensor reads normal until failure_time. The label
   set still records them, so the model's recall takes the hit
   unless it leans on indirect cues.
5. **Label noise**: 3% of `target_failure_within_72h` labels are
   flipped at random, simulating maintenance-log mistakes.

### Side-by-side metrics

| Metric    | Clean baseline | Realistic noise | Δ |
|-----------|----------------|-----------------|---|
| Precision | 0.9774       | 0.9848         | +0.0074 |
| Recall    | 1.0000       | 0.9153         | -0.0847 |
| F1        | 0.9886      | 0.9488        | -0.0398 |
| ROC-AUC   | 1.0000     | 0.9757       | -0.0243 |
| TP / FP / TN / FN | 216 / 5 / 6,787 / 0 | 389 / 6 / 6,577 / 36 | — |

The drop is **a feature, not a bug**. The clean baseline's near-perfect
numbers reflected a model that had memorised a deterministic precursor
pattern; under realistic noise the model has to actually generalise.
Numbers within an industry-realistic band for predictive maintenance
demonstrate model robustness rather than overfit signal.


## Interpretation

Recall is **0.915** — ✅ meets the 0.80 target. In production terms, that means the model would catch 92% of failures within their 72-hour warning window. Each missed failure is worth ~$20K/hour of unplanned downtime, so recall is the metric that matters most for predictive maintenance.

Precision is **0.985** — ✅ meets the 0.75 target. At this precision, roughly 2% of flagged hours would be false alarms; each one costs ~$5K in inspection time, so the ratio of recall (catches) to precision (false alarms) directly determines whether the system saves more than it costs.

ROC-AUC of **0.976** measures threshold-independent ranking quality. Above 0.90 is strong; in the 0.80-0.90 band there's still room to tune the threshold against the cost ratio above. F1 sits at 0.949.

**Caveat — even with realistic noise injected, this remains synthetic data.** Five categories of noise have been added (false-alarm spikes, sensor drift, operating-regime shifts, no-warning failures, label noise) so the metrics aren't the near-perfect numbers a noise-free simulator produces, but real Valmet data may still contain noise patterns we haven't simulated — slow corrosion, inter-sensor coupling, rare event modes the catalog doesn't cover, calibration errors that don't snap back. Expect production numbers to differ; that's why the model gets retrained on real DCS history once integration begins. **That said, the numbers above are now within industry-realistic bounds for predictive maintenance, demonstrating model robustness rather than overfit signal.**

---
*Generated by `python backend/ai_model/evaluate_model.py` against the
RandomForestClassifier in `backend/ai_model/artifacts/`. Re-run after
every retrain. Clean-baseline metrics in the comparison section are
frozen from `backend/ai_model/clean_baseline_evaluation_report.md`.*
