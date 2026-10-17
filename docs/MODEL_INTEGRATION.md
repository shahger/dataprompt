# Alfia: notebook-to-service integration

The service runs offline on Linux amd64 / Intel CPU. No cloud AI, CUDA, runtime downloads,
audio analysis, or face identification. Supply commercially permitted model weights and
verified regulatory sources; the scaffolding implements neither inference nor a laws database.

## Model contract

Copy `model_service.py.template` to root `model_service.py`. Export only notebook inference:
remove training cells, shell installs, notebook magics and hidden notebook state. Load weights
once at module import from `MODEL_DIR` (`/app/models` in Docker); place files under `models/`.

```python
def analyze_video(path, deadline=None):
    # path is a local uploaded video file. deadline is an absolute time.monotonic() value.
    # Check the deadline between inference steps and return accumulated partial results.
    return [{"type": "event type", "timecode_sec": 12.3,
             "description": "visible signs", "rule": "verified document, clause, text"}]
```

Return `[]` for no signs. `type`, `description`, and `rule` are strings; `timecode_sec` is finite,
nonnegative seconds. The service extracts JPEG evidence. It still supports `analyze_video(path)`;
if the function explicitly accepts `deadline`, the service passes the job submission time plus
`JOB_TIMEOUT_SEC`, minus a safety margin of `min(10 seconds, 10% of JOB_TIMEOUT_SEC)`.
The budget includes queue wait; a fresh budget is not started when a worker becomes available.
The template also caps inference at 240 seconds. Import failures are loud. Never print video
frames, base64, keys, or model exceptions that might contain payloads.

Add verified exact CPU package versions to `requirements-model.txt` (comment-only by default),
then `docker compose up -d --build --force-recreate api`. This file has its own cached Docker
layer after core requirements. Verify `/health`: `model_loaded: true`, `demo_mode: false`.
Keep `WORKERS=1` until inference thread safety and CPU thread counts have been tested.

## Optional local rules contract

Copy `rules_service.py.template` to root `rules_service.py` and implement:

```python
def lookup_rule(violation_type: str) -> dict | None:
    return {"rule": "verified document, clause, text"}  # or None
```

This fills only missing/blank model rules. Lookup failures are logged without payloads and
leave the rule empty; they do not fail the video job. Store an offline SQLite/JSON source in
`data/`, mounted read-only at `/app/data`, or use another table in the existing Postgres DB.
Use local paths/DB connections only and fast bounded queries. Empty `models/` and `data/`
folders work. Real data files are ignored by Git and excluded from image layers.

UI routes keep rule and description separate. For strict jury output (`INCLUDE_RULE=false`),
`RULE_IN_DESCRIPTION=true` appends ` Правило: <rule>` without adding a JSON field.

## Verify before handover

Use `scripts/check-public.ps1 -Video <video.mov>` for a smoke test (key stays internal).
Run `tools/eval_labels.py BASE_URL API_KEY DATASET_ROOT 3` for verdict and timecode checks,
and `tools/load_test.py BASE_URL API_KEY v1.mov v2.mov v3.mov v4.mov v5.mov` for concurrency.
The positional key is private; use the documented script for routine checks. Test the longest
video and a different camera angle. Five minutes is the per-video jury limit; with five jobs
and one worker, each must take roughly <54 seconds to fit the default queue-inclusive
270-second timeout, leaving time for upload and polling. Measure on the actual Intel laptop.
A watchdog cannot kill Python threads; cooperate with deadlines and return partial results.

For UI testing only, explicitly set the process environment `DEMO_MODE=true` and recreate the
API. Never enable it for jury use. It works only with no real model, labels its single result
ДЕМО, warns at startup, and exposes `demo_mode: true`. Unset it and recreate the API afterward.


## Local acceptance check and measured worker selection

1. Export notebook inference only into root `model_service.py`; keep training/magics out.
   Use the template, local `MODEL_DIR`, CPU providers and one-time loading. Put exact verified
   CPU packages in `requirements-model.txt`, weights in `models/`, and do not commit data/secrets.
2. Before starting FastAPI, run (repeat --video for several files):
   `python tools/check_model.py --video C:\data\short.mov --video C:\data\long.mov`.
   It checks imports and local imported Python files before execution, flags forbidden cloud
   SDKs, warns on literal URLs without displaying their values, suppresses model stdout/logs,
   validates finite JSON output and timecodes within duration + 1 second. Empty type/description,
   unexpected fields and non-string rules fail. The legacy and deadline signatures use the
   exact shared service invocation helper.
3. The default Python socket guard blocks non-loopback DNS/connect/connect_ex and sets
   HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, NO_PROXY=*. It wraps import and inference.
   `--no-offline-guard` is an explicit diagnostic escape hatch, not a deployment setting.
   This monkeypatch is not an OS sandbox: native libraries/subprocesses can bypass it.
4. Run `python tools/bench_model.py --videos C:\data\videos --count 5 --workers 1`.
   Directory entries are sorted MOV files; if N exceeds available files, inputs repeat without
   copying them. All N submissions share one monotonic submission time and queue-inclusive
   deadline. The table separates service time and completion since submission; p50/p95 use
   linear interpolation. Imports are loaded once, not charged per job. HTTP/upload/DB/evidence
   overhead is excluded, so leave a margin.
5. Add `--sweep` to actually measure W=1,2,3,4. It repeats N inferences at each worker count.
   The tool reports the largest safe MEASURED value among 1..4; unmeasured counts are unknown.
   Do not extrapolate CPU scaling from one worker. Compare last completion against 270 seconds
   (JOB_TIMEOUT_SEC), not just inference time. The rough queue estimate is ceil(k/W)*T, using
   T measured under that load. Five simultaneous videos with W=1 need <54 seconds each,
   plus margin for the jury's 300-second total upload-to-result limit.
6. Thread tests share the GIL, CPU and model memory. A fast fake/sleeping model is not a CPU
   benchmark. Threads cannot be killed: a model that ignores its deadline can hang these
   tools as well as a worker. Warm caches and thread oversubscription affect repeated runs.
7. Optionally implement `rules_service.py` against local SQLite/JSON in `data/` or local
   Postgres. lookup_rule fills only absent/blank rules and must be fast, bounded and offline.
   The tools validate the model contract; they do not build or validate a laws database.
8. Rebuild the image, run verdict/label evaluation and five-video load tests over real HTTP.
   The service now returns up to EVIDENCE_FRAMES=3 images around the event, ordered and
   deduplicated at video edges. This extraction adds CPU overhead after inference.
   Finish with prepare-handover.ps1; do not finalize jury text while the real model is absent.
