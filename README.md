# Cash discipline video analyzer

A FastAPI + Postgres service for local, CPU-only video analysis. Upload a video, receive a job ID, then poll for a verdict, timecodes and JPEG evidence. The browser UI is served at `/` and uses the same processing pipeline.

**No ML model is included yet.** Without `model_service.py`, readable videos finish with `no_violation` and `/health` reports `model_loaded: false`. This is a plumbing stub and provides no detection capability.

## Quick start: Windows PowerShell

Start Docker Desktop with Linux containers, then run:

```powershell
cd C:\dataprompt
Copy-Item .env.example .env
python -c "from pathlib import Path; import secrets; p=Path('.env'); p.write_text(p.read_text().replace('change-me-to-a-long-random-string', secrets.token_urlsafe(32)))"
# Strict official output; the UI will still receive rule fields:
Add-Content .env 'INCLUDE_RULE=false'
docker compose config --quiet
docker compose up --build -d
curl.exe http://localhost:8000/health
```

The key-generation command writes the random key directly into `.env` without printing it. Run the copy/generation once; preserve an existing `.env`. Open http://localhost:8000/. Expected stub health:

```json
{"status":"ok","model_loaded":false,"workers":1}
```

Only the API port 8000 is published. Postgres data lives in the `pgdata` volume; temporary uploads use the `uploads` volume. Models are mounted read-only from `./models`. The empty models folder contains only `.gitkeep` and requires no weights to start the stub.

After images have been built/pulled and model weights are available locally, start offline with `docker compose up -d --no-build --pull never`. Rebuilding from scratch still needs build dependencies and base images. The service itself makes no outbound calls during video processing. Health checks use localhost; the API connects to the local Compose database.

Stop with `docker compose down`. Finished jobs survive `restart api` and `down`/`up` as long as `pgdata` is retained. `docker compose down -v` deletes database data and must not be used if persistence is needed.

## Configuration

Compose reads `.env`; a direct `uvicorn main:app` invocation reads process environment variables, not `.env` automatically. Configuration is read at import/startup, so recreate the API container after changing it (`docker compose up -d --force-recreate api`).

| Variable | Default | Meaning |
|---|---|---|
| `API_KEY` | Required by Compose; direct Python fallback `change-me` | Jury header value. Set a random secret before use. Never commit `.env`. |
| `WORKERS` | `1` | Model worker threads in one API process. Must be a positive integer. |
| `INCLUDE_RULE` | `true` | `false` strips `rule` from jury responses; UI responses keep it. Use `false` for strict official JSON. |
| `JOB_TIMEOUT_SEC` | `270` | Positive finite seconds from job creation, including queue wait. Upload time is additional. |
| `UPLOAD_DIR` | Compose `/data/uploads`; direct Python `<project>/uploads` | Service-owned temporary directory. Startup deletes leftover `*.mov` files here. |
| `DATABASE_URL` | `postgresql://app:app@db:5432/app` | Postgres connection string. The default hostname works inside Compose. |
| `MODEL_DIR` | Compose `/app/models`; template `models` | Local weights directory read by model code. |

Keep default container paths unless you also adapt the volume mounts. `WORKERS` is independent of uvicorn processes: run **one uvicorn process, one API container** for this database and upload directory. Multiple API processes would each fail other processes' active jobs on startup and delete their uploads. The model function must be thread-safe before increasing `WORKERS`.

The image currently retains its root user: non-root writes to Docker Desktop named volumes could not be verified in Mode B. Requirements are copied before application code and pip uses a BuildKit cache mount. No platform-specific wheel URL, GPU package, cloud AI SDK or runtime model download is included.

## Public API

Every `/api/v1/*` request requires `X-API-Key`. Multipart field name is exactly `file`. Successful uploads return HTTP 200 immediately after storage/scheduling; poll the resulting job.

```powershell
$env:API_KEY = ((Get-Content .env | Where-Object { $_ -match '^API_KEY=' }) -replace '^API_KEY=', '')
curl.exe -X POST http://localhost:8000/api/v1/analyze -H "X-API-Key: $env:API_KEY" -F "file=@C:\data\video.mov"
curl.exe http://localhost:8000/api/v1/jobs/REPLACE_WITH_JOB_ID -H "X-API-Key: $env:API_KEY"
curl.exe -i http://localhost:8000/api/v1/jobs/unknown
```

`POST /api/v1/analyze` response:

```json
{"job_id":"32-character-UUID-hex"}
```

`GET /api/v1/jobs/{job_id}` responses (each variant has exactly the shown fields, apart from the optional rule extension described below):

```json
{"job_id":"...","status":"processing"}
```

```json
{"job_id":"...","status":"done","verdict":"no_violation","violations":[]}
```

```json
{
  "job_id":"...",
  "status":"done",
  "verdict":"violation",
  "violations":[
    {
      "type":"Model-provided violation type",
      "timecode_sec":0.4,
      "description":"Model-provided visual explanation",
      "evidence_frames":[{"timestamp_sec":0.4,"image_base64":"BASE64_JPEG_BYTES"}]
    }
  ]
}
```

```json
{"job_id":"...","status":"failed","error":"job timeout exceeded"}
```

`image_base64` is a JPEG encoded as base64 without a `data:` prefix. Timecodes are finite nonnegative numbers in seconds. Each violation has 1-3 evidence frames; this implementation emits one. Evidence timestamps describe the extracted frame and may differ from the model's event time when fallback is needed. A failed seek triggers a sequential search for the nearest decodable frame. When FPS metadata is absent, frame timestamps use an approximate 30 FPS fallback.

With default `INCLUDE_RULE=true`, each violation also has `"rule":"model-provided source"` (empty string if absent). This is an extension to the official schema. Set `INCLUDE_RULE=false` for the exact official result fields. The UI always retains the rule. Model import errors fail startup; model runtime exceptions produce a sanitized error such as `analysis failed (RuntimeError)` so exception text cannot leak keys or encoded frames.

| Condition | Response |
|---|---|
| Missing/wrong jury key | 401 `{"detail":"invalid api key"}` |
| Missing multipart `file` | 422 validation error (with valid key) |
| Empty file | 400 `{"detail":"empty file"}` |
| File exceeds 200 MiB (209715200 bytes) | 413 `{"detail":"file too large"}` |
| Unknown job | 404 `{"detail":"job not found"}` |
| Unreadable video | Upload accepted; job `failed` with `video cannot be opened or has no decodable frames` |
| Interrupted processing after restart | Job `failed` with `server restarted` |

`POST /ui/api/analyze` and `GET /ui/api/jobs/{job_id}` expose the same workflow without a key for the browser. These routes are public and can consume CPU. `GET /health` is public and returns `status`, `model_loaded`, and `workers`. `/docs` exposes the generated OpenAPI reference.

Uploaded files are removed on rejection, on worker completion/failure, or on next startup after interruption. Queued jobs canceled by a timeout have their files removed. **Python threads cannot be killed:** a timed-out running model keeps its worker slot and video until it returns; graceful shutdown also waits for it. The watchdog marks the database job failed and prevents late success from overwriting that status. A permanently hung model requires restarting the container; startup cleans leftover uploads. The watchdog retries a timeout update if the database is temporarily unavailable, but results cannot be retrieved while Postgres is down. Job records and base64 evidence remain in Postgres; uploaded videos are not retained for training.

## Tests and tools

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

Unit tests use a thread-safe in-memory `db` replacement and stub model. Tiny synthetic MOV videos are generated with OpenCV; no dataset is required. Tests cover auth, errors, both route families, processing/done/failed, real JPEG decoding, seeking fallback, rule filtering, queue timeout races, cleanup, simulated restart behavior, safe logs, CLI failures and the saved OpenAPI schema. The schema snapshot is `tests/api_contract.json`; an unintended public contract change fails the test.

To run the opt-in HTTP integration test against a stack **without a plugged-in model**:

```powershell
$env:BASE_URL = 'http://localhost:8000'
$env:API_KEY = ((Get-Content .env | Where-Object { $_ -match '^API_KEY=' }) -replace '^API_KEY=', '')
.venv\Scripts\python -m pytest -q -m integration
```

Without both environment variables, the integration test is skipped. It checks health, UI, auth, unknown job, missing file, generated upload, polling and the stub result over real HTTP. Persistence across real container restarts requires the manual check below; fake-database tests do not prove Postgres persistence.

```powershell
.venv\Scripts\python tools/test_client.py http://localhost:8000 $env:API_KEY C:\data\video.mov
.venv\Scripts\python tools/load_test.py http://localhost:8000 $env:API_KEY v1.mov v2.mov v3.mov
.venv\Scripts\python tools/eval_labels.py http://localhost:8000 $env:API_KEY C:\data\open 3
```

All tools support `--help`, `--timeout` (300 seconds), `--request-timeout` (30 seconds), and `--poll-interval` (2 seconds). Failed jobs, HTTP errors and timeouts exit nonzero. The smoke tool saves JPEGs with job/violation/frame-specific names (`--output-dir` selects the folder), never prints base64 or the key. The load tool measures concurrent upload-to-result wall time and exits nonzero if any video fails or finishes at/after 300 seconds. Without a real model these timings measure plumbing overhead only.

The evaluation tool reads `open_labels.xlsx` and `videos/*.mov`, matches Latin/Cyrillic names by number, and reports whole-video verdict accuracy and timecode hits among correctly predicted positive videos. Its timecode denominator intentionally excludes missed positive verdicts, as in the original tool. Missing labelled videos now fail explicitly instead of silently reducing the evaluated set. No dataset evaluation has been performed in this environment.

## Plug in the model

1. Copy `model_service.py.template` to `model_service.py`. Replace the TODO with notebook inference code and return a list of `{type, timecode_sec, description, rule}` dictionaries; return `[]` when no signs are detected. The template alone still performs no detection.
2. Put weights in `models/`. Load them once from `MODEL_DIR` at import time. Use CPU only, with no network calls, training steps, shell installs, cloud AI SDKs, or runtime downloads. Supply actual regulatory sources; the service invents none.
3. Add only required, verified, pinned inference dependencies to `requirements.txt`. Confirm commercial-use licenses and Linux amd64 compatibility. Avoid committing the dataset or weights.
4. Keep a cooperative inference budget below the watchdog deadline. The template uses a monotonic 240-second inference budget, but queue time also counts toward the service's 270-second deadline. Release decoder resources even on early exit; the template does so.
5. Rebuild with `docker compose up --build -d`, verify `model_loaded: true`, then measure the longest videos and five simultaneous submissions on the actual Intel laptop. Set model-library CPU thread counts explicitly and confirm thread safety before increasing `WORKERS`.

For N simultaneous videos, W worker threads, and per-video service time T measured under load, the last job takes roughly `ceil(N/W) * T` plus upload/polling overhead. With five videos and one worker, T must be below about 54 seconds to fit the 270-second watchdog (and leave more room for the jury's 300-second deadline). More workers may slow each inference through CPU contention. The unbounded in-process queue and public UI routes are additional load risks; a watchdog failure is still an unprocessed video for scoring.

## Docker verification checklist (not yet executed here)

After Docker Desktop's engine is available:

1. Build and start from the quick-start commands; record build time (`Measure-Command { docker compose build }`) and image size (`docker image inspect (docker compose images -q api) --format '{{.Size}}'`). Confirm each command succeeds.
2. Run the integration test and the smoke/load tools with generated MOVs. Expect `model_loaded: false` and `no_violation` while the model is absent. Confirm an empty weights folder works.
3. Keep a completed job ID. Run `docker compose restart api`, wait for health, and retrieve that ID. Then run `docker compose down`, `docker compose up -d`, wait for health, and retrieve it again.
4. Verify non-root volume permissions before adopting a non-root Docker user. The current Dockerfile intentionally retains the original user because that check could not run here.
5. Finish with `docker compose down`.

See `docs/VERIFICATION.md` for the actual checks, limitations and fixes. No image size, build time or real-stack performance number has been measured yet.

## Troubleshooting

| Symptom | Cause / action |
|---|---|
| `dockerDesktopLinuxEngine` pipe missing | Start Docker Desktop and wait for the Linux engine; CLI installation alone is insufficient. |
| Compose says `Set API_KEY in .env` | Create `.env`, set the key, run from the project root. Use `docker compose config --quiet` to validate without printing secrets. |
| API cannot connect to DB | Check `docker compose ps` and `docker compose logs db`; retain the Postgres health dependency. |
| UI missing or API unexpectedly 404 | Keep `static/index.html` and the static mount after all API routes. |
| `model_loaded: false` | `model_service.py` is absent from the built image. Copy the template, implement inference and rebuild. |
| Model import failure | Missing dependency or local weight; startup intentionally fails. Inspect the model's own code without logging secrets or frames. |
| Timeout despite low CPU activity | A model may be hung, or a job may be waiting behind earlier work. A thread timeout does not free a running worker. |
| Uploaded file cannot be decoded | Inspect codec/container validity locally. Fake unit videos do not prove all camera codecs work. |
| Slow image build | Cache/pre-download dependencies before the event and keep the pip cache mount. |
| `models/` bind mount error | Create the directory; keep the project outside OneDrive and use Docker Desktop file sharing. |
| Mac-built image fails on Intel | Build on the deployment laptop, or explicitly build Linux amd64 with the proper builder. |
| httpx TestClient deprecation warning | The installed Starlette still supports the requested httpx test client; tests pass. Review the testing stack before upgrading it. |

## Jury run and usage instructions

Fill the addresses and share the key privately when deployment and model validation are complete:

- UI: `https://[public-host]/`
- API base: `https://[public-host]/api/v1`
- Credential: privately supplied key in header `X-API-Key`
- Upload: `POST /api/v1/analyze`, multipart field `file`; keep `job_id`.
- Result: poll `GET /api/v1/jobs/[job_id]` about every two seconds for `processing`, `done`, or `failed`.
- For `done`, inspect `verdict`, each violation's type, timecode, description and JPEG evidence. UI output also shows the rule/source.

Browser use: open the UI, select a `.mov`, click Analyze, wait for the result, and review timecodes/evidence/rules. A result describes possible signs for a human reviewer. The processing target has not been measured with a real model. Uploaded videos are deleted after processing, with the hung-thread limitation described above.

Local operation: install Docker Desktop, create `.env` and configure `API_KEY`, run `docker compose up --build -d`, and open http://localhost:8000/. Keep the laptop powered and awake during jury testing. Before handover, supply the team-authored architecture/models, actual regulatory sources and mapping, recognized violation types, and limitations documents. Public hosting/tunnel setup is outside this repository task and has not been configured.
