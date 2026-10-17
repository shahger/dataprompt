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
