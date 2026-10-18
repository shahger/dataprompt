# Model: possible cash-discipline violations

The model runs fully locally on CPU, with no network access and no cloud AI.
- Its result is a pointer for a human reviewer, not a verdict.
- Every model and its licence is listed in [MODELS_LICENSES.md](MODELS_LICENSES.md).

## Pipeline (`ml/`, entry point `model_service.analyze_video`)

```
video → 3 fps frames → RT-DETRv2-R18 detector (ONNX) → ByteTrack (people) + static objects
      → DINOv2-small crop features → heads: person role, safe/door/laptop state, person action
      → scene timeline (smoothed states, client sessions, money ledger)
      → one rule per violation type → calibrated thresholds → type, timecode, description, rule
```

- **Zones and roles** are derived from each video. There are no hard-coded pixel regions, so the pipeline follows a new camera angle.
- **Citations** come only from `rules/rules_db.json`, built from the НБРК catalogue. Every quote is checked word for word against the official text.
- **V-PC (laptop left on)** is low severity. Its description says there is no direct prohibition.
- **Descriptions** state what is visible, the model score (0–1) and «требуется проверка».
- **Evidence frames** are extracted by the service at the timecode ±1 s.

## Honest evaluation (40 training videos, leave-one-pair-out)

Each violation video is held out together with its clean twin.

| Metric | Value |
|---|---|
| Recall (violation videos flagged) | 0.90 (19/21) |
| False-positive rate (clean videos flagged) | 0.79 (15/19) |
| Some finding within 6 s of the labelled moment | 0.62 |
| Correct type within 6 s | 0.24 |
| Video-level AUC | 0.66 |

- The operating point follows the brief: **a missed violation is unacceptable**. That costs false positives.
- The rules alone, fed with perfect (annotated) perception, reach 0.71 type accuracy. The gap is perception: actions, and the safe state, whose door faces away from the camera.

## Speed (this Docker stack, Mac, WORKERS=1)

| Video | Time |
|---|---|
| Typical 15–60 s clip | 8–45 s |
| Longest training video (142 s) | 67 s |

Measure on the deployment laptop with `tools/bench_model.py`.

## Updating the model

1. Retrain in the ML repo.
2. Copy `models/detector/{detector.onnx,config.json,preprocessor_config.json}`, `models/heads.joblib` and `models/rule_params.json` into `models/`.
3. Recreate the API container.

The `ml/` package must be the same version that produced the weights.
