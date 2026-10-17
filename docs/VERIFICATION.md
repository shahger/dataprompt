# Environment check (Step 1)

- Docker client: 29.8.2, windows/amd64, context desktop-linux.
- Docker Compose: v5.6.0.
- Docker server/info: unavailable; named pipe dockerDesktopLinuxEngine does not exist.
- Python: 3.13.7; pip: 25.2.
- Network: pip download requests succeeded after sandbox network approval (requests 2.34.2).
- Mode B: Docker engine unavailable. No image pull/build or real Postgres stack verification is possible in this state.

Step 0 moves (original files preserved by moving):
- index.html -> static/index.html
- test_client.py -> tools/test_client.py
- load_test.py -> tools/load_test.py
- eval_labels.py -> tools/eval_labels.py
- datathon26_handoff_en.md -> docs/HANDOFF.md

Created models/.gitkeep and .gitignore; existing .dockerignore and .env.example were present.

## Completed work and evidence

- Step 2: replaced unbounded whole-file application reads with 1 MiB copy chunks and a 200 MiB file limit; rejected empty files; ensured rejected/scheduling-failed uploads are removed; offloaded blocking work; made executor startup/shutdown lifespan-managed; made the static directory independent of the working directory; switched to full UUID job IDs; validated responses and model timecodes. Missing/wrong keys are checked as a dependency, including requests missing the file field.
- Postgres review: the original psycopg 3 connection.execute(), Jsonb adaptation, placeholders and per-operation connections were already correct. Added a connection timeout and guarded terminal updates with WHERE status='processing'. No shared connection is used across threads. Real SQL execution is unverified.
- Step 3: added FastAPI TestClient tests with a thread-safe fake db and stub analyze_video; synthetic MOV generation and actual JPEG decoding; OpenAPI contract snapshot. Runtime and dev packages installed successfully on Windows Python 3.13.7.
- Step 4: Mode B, so no real stack was run. Added an opt-in integration test (BASE_URL + API_KEY) for later real HTTP verification. Docker daemon named pipe was missing; no image pull was attempted. Image size, build time, Postgres persistence, generated-video real-stack timings and real tools-against-stack timings are unavailable. No containers were started, so none were left running by this task.
- Step 5: invalid/corrupt video now fails even with the stub; failed/unsupported seeking searches sequentially for nearest readable evidence; emits one frame (within required 1-3). Added INCLUDE_RULE (default true), queue-inclusive JOB_TIMEOUT_SEC (default 270), terminal-state locking plus DB guard, timeout retries after DB outage and cancellation/cleanup of expired queued jobs. Job completion logs contain JSON fields job_id, duration_sec, verdict only. Model exception text is not logged or returned.
- Step 6: PyYAML successfully parsed Compose and verified the Postgres health dependency; retained requirements-first layers and pip cache mount; excluded .env, virtual environment, downloads, temporary test files and model weights from build context. Added API healthcheck; Compose now requires API_KEY. Retained original root image user because named-volume permissions cannot be verified without Docker.
- Step 7: tools now have argparse help, request/poll deadlines, checked HTTP/JSON errors and nonzero failures; smoke evidence filenames no longer collide across violations. Load timing still covers concurrent upload-to-result; label evaluation retains the original conditional localization denominator and fails on missing labelled files. Added tool tests, README quick start/env/API/model/troubleshooting/jury instructions, and safe decoder cleanup/monotonic budget in the model template. No ML model, weights, dataset, tunnel or external publication was added.

### Verified dependencies

Runtime direct pins: fastapi 0.137.2, uvicorn 0.49.0, python-multipart 0.0.32, opencv-python-headless 5.0.0.93, psycopg[binary] 3.3.4. Removed unused aiofiles. Dev pins: pytest 9.1.1, httpx 0.28.1, requests 2.34.2, openpyxl 3.1.5, PyYAML 6.0.3.

All direct pins were downloaded and installed into the project virtual environment. A separate binary-only pip download also resolved every runtime requirement and dependency for CPython 3.11 on Linux amd64 (manylinux2014 / manylinux_2_28). This verifies available wheels, not successful image execution. Linux wheels are not hardcoded into the Dockerfile.

### Test result

Final suite run: `25 passed, 1 skipped` (3.15 seconds). The skipped test is the real-stack integration test. One upstream Starlette warning says httpx TestClient support is deprecated; support still works and all requested httpx tests pass. No warning was suppressed.

The initial sandbox test run could not create pytest temporary directories. The successful run used an approved command with TEMP and TMP set to C:\dataprompt\.test-artifacts, so test artifacts stayed inside the project. Python compilation, all tool --help commands and Compose YAML parsing also passed. Unit tests include simulated restart persistence; this does not establish actual Postgres/volume persistence.

### Remaining limitations

- No Docker engine: real build/start/HTTP checks, restart/down-up persistence, image size/build time, non-root permissions and actual Docker Desktop runtime compatibility remain unverified.
- No real model or dataset: detection quality, supported camera codecs, longest-video inference and five-concurrent-video timing remain unmeasured. No model license or regulatory reference is claimed.
- Stub-only timings would measure plumbing overhead, not detection speed; no real-stack timing was produced.
- A running Python thread cannot be killed. Timeout sets failed, but the worker slot/video remain until that thread returns; graceful shutdown waits too. Restarting the container terminates stuck threads and startup clears leftover uploads. A queued timeout can cancel and delete immediately.
- WORKERS=1 with five jobs needs roughly <54 seconds per video to fit the default 270-second queue-inclusive deadline, allowing additional upload/poll overhead before 300 seconds. CPU oversubscription, many evidence fallbacks, unbounded queue depth, public UI submissions and slow networking can consume that margin.
- Use one API process/container with its own database and service-owned upload folder. API and UI response schemas are guarded; INCLUDE_RULE=false is required for strict official fields.
