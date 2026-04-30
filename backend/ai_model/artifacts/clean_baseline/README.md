# Clean-baseline model snapshot

These artifacts were trained on the deterministic synthetic data set (no
sensor noise, no operating-regime shifts, no label noise — just the 16
stratified failure precursors from Phase 2). They are kept here as a
**safety fallback** for the realistic-noise iteration in
`claude/realistic-noise-and-baseline`.

## Metrics on a time-based 80/20 holdout

| Metric    | Value  |
|-----------|--------|
| Precision | 0.9774 |
| Recall    | 1.0000 |
| F1        | 0.9886 |
| ROC-AUC   | 1.0000 |
| Confusion | TP=216 FP=5 TN=6,787 FN=0 |

(Full report: `backend/ai_model/clean_baseline_evaluation_report.md`.)

These numbers are intentionally near-perfect — they reflect a model that
has memorised a deterministic precursor pattern. The realistic-noise
iteration is expected to drop these metrics into a more credible band
(target ≥0.75 precision, ≥0.80 recall) by injecting the same kinds of
artefacts a real Valmet DCS stream contains: false-alarm spikes, slow
sensor drift, operating-regime shifts, no-warning failures, and
mislabelled events.

## Why we keep this checkpoint

If the noisy retrain comes in below the demo-acceptable thresholds and
two tuning cycles fail to recover them, we revert to this snapshot so
the demo never ships a degraded model. The realistic-noise simulator
itself remains valuable engineering work either way (it surfaces
failure modes we'd otherwise miss in production), but the model that
goes to production is whichever side of the comparison meets targets.

## How to revert to this baseline

```bash
cp backend/ai_model/artifacts/clean_baseline/*.pkl  backend/ai_model/artifacts/
cp backend/ai_model/artifacts/clean_baseline/feature_schema.json  backend/ai_model/artifacts/
cp backend/ai_model/artifacts/clean_baseline/metrics.json          backend/ai_model/artifacts/
```

After reverting, restart any process that lazy-loads the models
(`predict.reset_cache()` is exposed for tests; uvicorn workers
hot-reload on file change).

## File inventory

| File                        | Purpose                                       |
|-----------------------------|-----------------------------------------------|
| `failure_probability_rf.pkl`| RandomForestClassifier — supervised model     |
| `anomaly_isoforest.pkl`     | IsolationForest — unsupervised anomaly score  |
| `feature_schema.json`       | Trained feature column order + normalisation  |
| `metrics.json`              | RF + isolation-forest training metrics        |
