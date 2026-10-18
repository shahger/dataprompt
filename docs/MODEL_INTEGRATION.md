# Integrated model and artifact contract

The production adapter is `model_service.py`; inference is implemented in `ml/`.
It loads the Analyzer once at import. Do not replace it with the old template when deploying
this release. Training and full leave-one-pair-out evaluation belong to the team's ML project.

## Required local artifacts

Obtain the complete trained bundle that matches this version of `ml/`, and place it under:

```text
models/
  detector/
    detector.onnx
    config.json
    preprocessor_config.json
  encoder/
    dinov2-small/
      config.json
      preprocessor_config.json
      model.safetensors             # Or the complete equivalent Transformers checkpoint
  heads.joblib
  rule_params.json
```

Retain all files from the supplied encoder directory, including any checkpoint index/shards.
The detector's `config.json` defines class names. `heads.joblib` contains the trained role,
state and action classifiers plus encoder metadata. `rule_params.json` contains calibrated
thresholds and offsets. Copying a generic detector cannot reproduce these trained artifacts.

Weights are excluded from Git and Docker image layers. Compose mounts `./models` read-only
at `/app/models`. The detector, heads and rule parameters use `MODEL_DIR`; the current crop
encoder resolves `models/encoder/<name>` relative to the project root. Keep the standard
Compose mount for this adapter. Missing artifacts cause startup to fail, rather than silently
substituting a demo result. Only load a weights/joblib bundle supplied by the model author.

The regulatory database is already included as `rules/rules_db.json`. The runtime does not
need an external laws database or a separate `rules_service.py` to obtain these citations.

## Inference interface

```python
def analyze_video(path, deadline=None):
    # Return [] or a list of events from real local inference.
    ...
```

An event has `type` (nonempty string), `timecode_sec` (finite nonnegative seconds),
`description` (nonempty string), and `rule` (string). `[]` means no events found.
The adapter converts the pipeline report to this service contract. FastAPI extracts evidence
and formats the jury/UI responses; the public API schema is unchanged.

The jury schema uses `INCLUDE_RULE=false`. With `RULE_IN_DESCRIPTION=true`, a nonempty rule
is appended to `description`; the UI keeps `rule` separate.

## CPU environment and startup

Dependencies are pinned in `requirements-model.txt` and installed in a separate Docker layer.
The image uses Python 3.12 and CPU inference. Compose sets `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`. Weights must be present before startup; downloads are not part of
inference. Configure the deployment machine's own private `.env` before starting:

```powershell
docker compose up -d --build
curl.exe http://localhost:8000/health
```

Readiness flags are `model_loaded: true` and `demo_mode: false`. After replacing only bind-mounted
weights, restart the API outside judging. After changing source/dependencies, rebuild/recreate it.
A new host needs its own Docker images, private configuration and complete artifact bundle;
a Git clone does not transfer them.

## Queue, threads and deadlines

- Use `WORKERS=1` for this adapter. Its shared Analyzer mutates `det_stride` per call.
- Compose defaults to `FORTE_THREADS=6` for CPU inference threads.
- `JOB_TIMEOUT_SEC=270` includes queue wait. The service passes an absolute monotonic deadline,
  with a safety margin of `min(10 seconds, 10% of JOB_TIMEOUT_SEC)`.
- The current adapter increases detector stride when less than 120 seconds remain. It does not
  interrupt inference or return accumulated partial findings when the deadline is reached.
- The watchdog can mark a job failed, but cannot terminate the Python thread. A late result
  cannot overwrite a terminal job; the worker/file can remain occupied until inference returns
  or the process restarts. Do not restart the service during jury requests.

## Validation tools

Run these in a Python environment with both development and model dependencies installed,
or inside the matching API container with the test files mounted:

```powershell
python tools/check_model.py --video C:\data\short.mov --video C:\data\long.mov
python tools/bench_model.py --videos C:\data\videos --count 5 --workers 1
.\scripts\check-public.ps1 -Video C:\data\video.mov
```

The checker scans local imports, rejects cloud inference SDKs, warns on literal URLs without
printing their values, validates JSON fields and timecodes, and suppresses model payload output.
Its default Python socket guard blocks non-loopback connections and sets offline flags.
This is a diagnostic guard, not an OS sandbox. `--no-offline-guard` is a diagnostic override.

The benchmark reports service time and queue-inclusive completion time. It excludes network
upload, database work and service evidence extraction. `--sweep` can measure 1–4 workers for
adapters designed for concurrency; it does not establish thread safety for this shared Analyzer.
With one worker, five jobs share the same queue budget; timings on one clip or another CPU
do not establish concurrent public HTTP latency.

Legacy API evaluation tools use these argument layouts:

```text
python tools/eval_labels.py BASE_URL API_KEY DATASET_ROOT 3
python tools/load_test.py BASE_URL API_KEY v1.mov v2.mov v3.mov v4.mov v5.mov
```

Use a private terminal: positional keys can appear in process arguments. For routine smoke
tests, `check-public.ps1` reads the local key internally without printing it. `DATASET_ROOT`
for `eval_labels.py` contains `videos/` and `open_labels.xlsx`; the spreadsheet uses one row
per video with filename, timestamp and verdict. That tool reports verdict accuracy and
localization conditional on correctly predicted positive videos. It is not the ML project's
full type/rule/leave-one-pair-out evaluator.

Model evaluation methodology and reported metrics are in [MODEL.md](MODEL.md).
Application tests use mocked model inference; the opt-in legacy live-stack test expects a
stub and must not be aimed at the deployed integrated model.

## Optional rule extension

`rules_service.py.template` remains an extension point: `lookup_rule(type)` returns
`{"rule": "document, clause, text"}` or `None`. It fills only a blank model rule.
Lookup failures leave the rule empty without failing the job. Additional offline data may
use `data/` (read-only mount) or another local PostgreSQL table. The integrated model already
returns citations from `rules/rules_db.json`.

## Operational checks

Use `scripts/status.ps1` for local/public health. `scripts/prepare-handover.ps1` additionally
checks configuration, repository cleanliness and the final jury document. Run these on the
actual host; a clean source checkout alone does not prove deployment readiness.
The final jury document has no pre-model block. `-Finalize` remains an idempotent maintenance
option and is unnecessary for an already finalized document. Keep demo mode disabled.
