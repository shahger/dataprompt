# Datathon '26 (ForteBank case): full handoff summary

Purpose: paste this whole file into another AI chat and continue working. It is written so the next assistant can immediately help you **build, run and ship** the service. The API section (section 3) is the most detailed on purpose.

**Honesty notes.** Everything marked "not verified" was never executed by me (the previous assistant): the FastAPI + Postgres stack, the browser UI, the tools scripts and the Docker build of the skeleton were only syntax-checked. Verified in a sandbox: the label file parsing, OpenCV seek-by-timestamp frame extraction on the dataset `.mov` files, and decode speed (section 5).

**Corrections to earlier notes.** The user (Shah) does **not** study at Nazarbayev University; ignore any earlier statement saying so. The workshop speaker "Fatikh Barysh Aidyn" is a different person from teammate "Aidyn".

---

## 0. TL;DR build order (what to do, in order)

1. Copy the `api_skeleton` files (section 7) into a folder, e.g. `C:\dev\cashier-api`. Rename `.env.example` to `.env` and put a long random key in it.
2. `docker compose up --build`, then open http://localhost:8000 (UI) and http://localhost:8000/health.
3. Run `tools/test_client.py` against `http://localhost:8000` with any `.mov` (expected right now: `done` / `no_violation`, because no model is plugged in yet).
4. When Alfiya delivers the notebook: run it in Docker Jupyter, extract inference into `model_service.py` (section 9), add libraries to `requirements.txt`, put weights in `models/`, rebuild.
5. Run `tools/eval_labels.py` (accuracy + timecode check on the 42 labelled videos) and `tools/load_test.py` (5 videos at once must all finish < 300 s).
6. Open a public tunnel (section 6), test the public URL from a different network (phone on mobile data), then hand the jury: UI URL, API base URL, API key, run instructions (template in section 10).
7. Keep the laptop awake and plugged in; do not restart the service during jury checking.

---

## 1. People, team, context

- **User:** Shakh (Shakhriyar Yerzhanov AKA Shakh Yerzhan AKA Shah AKA Shakh). Windows 11, Intel CPU, Docker Desktop (installed, `hello-world` works, `docker build` works), VS Code. Chats in English; technical terms in English. Student of Astana IT University.
- **Team of 3:** Shah, Alfiya (Also known and written in this file as Alfia), Aidyn. **No NVIDIA GPU in the team.** Hardware: two Intel laptops (one is Shah's Windows 11 machine) and Alfia's MacBook (chip not known: Intel or Apple Silicon but probably M1-M4).
- **Event:** DATATHON '26, NU Data Science Club (DataSci), case partner ForteBank, supported by NU Impact Foundation, prize pool 3,000,000 KZT, 24 hours, offline at Nazarbayev University (Astana). Workshop was 16.10.2026 19:00. Datathon the next day: check-in 09:00 Orange Hall, dataset revealed 11:00, 24h timer starts 12:00, **deadline 12:00**, finalist pitches 18.10 13:00, closing 18:00. Contacts: Telegram @nu_datasci, datascience@nu.edu.kz, datathon.com.kz.
- **Roles (from Alfia's plan):**
  - **Alfia:** data analysis, watching the videos, training the model in a **Jupyter notebook**, then hands the notebook to Shah. Also the written docs: architecture/approach/models, regulatory sources and rule-to-video mapping, list of violation types, limitations and known errors.
  - **Shah:** public service address (UI + API), API key for the jury, run/usage instructions, **Docker DB container** where videos submitted by the jury are handled, the whole server workflow (accept video -> process -> return result), understand how to submit the server, where to host it, how to give the API key, hardware constraints.
  - **Aidyn:** sketch of the interface in ForteBank style (he handles his part himself).
  - Plan from Alfia: first understand the structure (only teams with a working API reach the pitch), then basic workflow, then interface (Aidyn) and DB container (Shah); look at the videos together.

---

## 2. The case (technical brief, condensed)

**Task:** "AI service for detecting cash-desk discipline violations from video". Build and deploy a working service with a UI where a customer uploads a video of a cashier. The service reports whether signs of a violation are present and, if so, shows evidence frame(s), timecode and the rule / regulatory source. Output is a hint for a human reviewer, not a legal conclusion.

**Mandatory user flow:** (1) open web UI, upload video; (2) service shows processing status; (3) result is either "no violation detected" or "signs of possible violations detected"; (4) per violation (several per video possible): type, timecode, description; (5) one or more evidence frames; (6) short explanation of what is visible and why it may be a violation; (7) rule and regulatory source (document name, clause/section); (8) the same service must also be reachable by API.

**Hard constraints:**
- **Fully local.** All models run inside the team's deployed service. Cloud AI services/APIs (cloud LLMs, multimodal models, recognition services) are forbidden during video processing, including sending them video, frames or frame descriptions. Disqualification for cloud AI APIs or ready-made solutions.
- **Portable.** After weights are downloaded the service must not need internet to process video (so it can move into the bank's internal network).
- Strictly visual: **no audio**, **no face recognition/identification**.
- No claiming a violation if it needs data not visible in the video (e.g. correctness of a booking entry).
- Pretrained models / third-party code are allowed only if open source with a license that allows **commercial use**. Extra data (own recordings, synthetic, open datasets) is welcome.
- Regulatory sources: only Republic of Kazakhstan acts (NBRK, adilet.zan.kz). Links without an exact clause are accepted; other banks' open documents are accepted. Invented references are penalized.
- No GPU or cloud credits from the organizer. A **public URL is mandatory**. No auth / history / export / batch upload needed. UI language is the team's choice.
- ForteBank may use the solution commercially after the hackathon. Dataset only for use within the hackathon.

**Deliverables:** working service address (UI), API address and API key for the jury, run/usage instructions, short description of architecture/approach/models, description of regulatory sources and the rule-to-video mapping principle, list of recognized violation types with short descriptions, list of limitations and known error cases.

**Scoring (100):** detection quality 25, localization (timecode + evidence frame) 15, classification of type 15, rule grounding 15, robustness (unseen videos, other camera angle) 10, product readiness 10, technical solution (architecture, locality) 10.

**Other FAQ facts:** test set is 5+ videos, uploaded remotely by the jury via the team's link, **the final test video is filmed from a different angle**, scoring is automatic from JSON, criterion 1 is judged per whole-video verdict, abusing "insufficient data" without justification is penalized. **For the bank, false positives must be as rare as possible and a missed violation is unacceptable.** "Omission" violations (cashier did not perform a required action) and their timecode are up to the team. Pitch for shortlisted teams only: 5 min + 2 min Q&A, slides optional; ties are decided at the pitch.

---

## 3. API deep dive

### 3.1 What the jury does (and why the API decides everything)
The jury runs their own test videos through **every team's API automatically**, collects the JSON results, and only the best teams are invited to pitch. So: **no working public API = no pitch.** Treat the API as the product's contract, not an afterthought.

### 3.2 Endpoints (official)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/analyze` | Upload a `.mov` as multipart field `file`. Returns `{"job_id": "..."}` immediately. |
| GET | `/api/v1/jobs/{job_id}` | Returns status `processing`, `done` or `failed`, plus the result when `done`. |

- Auth: header `X-API-Key: <key>` on every call. Missing/wrong key -> reject (we return HTTP 401). The team creates the key and gives it to the jury together with the base URL.
- If the service is unreachable or returns no result within **5 minutes**, the video counts as unprocessed.
- Example from the brief: `curl -X POST https://team.example.kz/api/v1/analyze -H "X-API-Key: <key>" -F "file=@video_017.mov"`

### 3.3 Result schema (when `status` = `done`)
```json
{
  "job_id": "3f2a9c1e",
  "status": "done",
  "verdict": "violation",
  "violations": [
    {
      "type": "Violation type name",
      "timecode_sec": 44.2,
      "description": "What is visible and why it is a possible violation",
      "evidence_frames": [ { "timestamp_sec": 44.2, "image_base64": "/9j/4AAQ..." } ]
    }
  ]
}
```
- `verdict`: exactly `violation` or `no_violation`. `violations`: empty list when none. `evidence_frames`: 1-3 JPEG frames, base64 (no `data:` prefix).
- `processing` response in our implementation: `{"job_id": "...", "status": "processing"}`. `failed`: `{"job_id": "...", "status": "failed", "error": "..."}` (a failed job counts as unprocessed for scoring, so avoid failures: prefer a partial result).
- **Extra field:** our implementation adds `"rule"` to each violation (for the UI). It is NOT in the official schema. If the automatic checker proves strict, remove it from the API output and keep it in the UI only.

### 3.4 Why two steps (async job pattern)
Processing takes tens of seconds to minutes; an HTTP request should not stay open that long (browsers, tunnels and proxies cut long requests). So: `POST` stores the file, creates a job row (status `processing`), puts the job in an in-process queue (ThreadPoolExecutor) and returns the `job_id` at once. A worker runs the model and writes the result into Postgres. The client polls `GET /jobs/{id}` every ~2 s.

```
client --POST file+key--> API --save file, INSERT job(processing)--> returns job_id
                           |--> worker thread: analyze_video(path) -> frames -> UPDATE job(done, result)
client --GET /jobs/id--> API --SELECT--> {"status":"processing"} ... later {"status":"done", ...}
```

### 3.5 Design decisions in the skeleton
- **FastAPI** + `uvicorn`. `x_api_key: str = Header(None)` automatically maps to the `X-API-Key` header.
- **Jury routes** `/api/v1/...` require the key. **Browser UI routes** `/ui/api/...` do not (the UI is served by the same app from `static/`, so no key leaks into browser JavaScript). Risk: anyone who knows the URL can use the UI route and burn your CPU. Mitigation: single small queue, 200 MB upload cap; optionally put the UI behind a simple shared password later.
- **Postgres** stores jobs (survives restarts); on startup stale `processing` jobs become `failed`. Uploaded videos are saved to a volume only while processing and **deleted afterwards** (jury videos must not be kept/used for training).
- `analyze_video(path)` is the only place the model plugs in. Frame extraction by timestamp (OpenCV) and JPEG/base64 encoding are done by the service, not the model. If `model_service.py` exists it is imported (import errors are loud); if not, a **stub** returns `no_violation` and logs a warning. `/health` reports `model_loaded`.
- Models are loaded once at import time, never per request. No internet at runtime (weights come from `models/`).

### 3.6 Time budget and queue math (critical)
- Video up to 145 s at ~30 fps is ~4,350 frames. Sandbox measurement (single core, **not** your laptop): decoding the 142 s video X-14 and keeping 2 frames/s (285 frames) took **7.0 s**. Decoding is cheap; **model inference is the bottleneck**.
- With `W` workers, per-video time `T` (measured under parallel load) and `N` videos submitted at once, the k-th video finishes at about `ceil(k/W) * T`. You need `ceil(N/W) * T` well under **300 s**. Example: N=5, W=1 means T must be under ~55 s; W=2 means T under ~95 s (but two parallel workers slow each other down on a few cores). **Measure with `tools/load_test.py`**, do not guess.
- Budget guess for CPU inference: sampling ~2 frames/s on a 145 s video is ~290 frames, so roughly 0.2-0.3 s per frame at most if the target is 60-90 s per video.
- **Return a partial result before the deadline instead of nothing:** `model_service.py.template` stops analysing at `JOB_BUDGET_SEC = 240` and returns what it has found. An unprocessed video is worse than a partial answer.
- Set ONNX Runtime / PyTorch thread counts explicitly when running several workers so they do not oversubscribe the CPU.

### 3.7 Error behaviour
| Case | Response |
|---|---|
| Missing/wrong `X-API-Key` | 401 `{"detail":"invalid api key"}` |
| No `file` field | 422 (FastAPI validation) |
| File larger than 200 MB | 413 |
| Unknown `job_id` | 404 |
| Model/code exception | job status `failed` with `error` text (logged with traceback) |
| Server restarted mid-job | job becomes `failed` ("server restarted") on next startup |

### 3.8 API test checklist (do all before handing over the key)
1. Without header -> 401; with a wrong key -> 401; with the right key -> 200 and a `job_id`.
2. `GET` with the `job_id` goes `processing` -> `done`; unknown id -> 404.
3. Upload the biggest dataset video (~29 MB, X-14) through the **public** URL (tunnels may limit body size; Cloudflare's free plan reportedly caps request bodies around 100 MB, verify).
4. `tools/load_test.py` with 5 videos at once: worst time must be under 300 s.
5. `tools/eval_labels.py` over all 42 labelled videos: verdict accuracy and timecode hit rate (tolerance 3 s by default).
6. Call the public URL from another network (phone on mobile data), not only from your own Wi-Fi.
7. Restart the stack once (`docker compose restart`) and confirm it comes back by itself.
8. Check `evidence_frames[*].image_base64` decodes to a valid JPEG (the test client saves them as files).

### 3.9 How the API key is created and given
Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Put it in `.env` (`API_KEY=...`), never in Git. Give the jury: base URL, key, header name `X-API-Key`, and a curl example (template in section 10). Rotate the key after the event.

---

## 4. Dataset facts (from `open.zip`)

- 42 videos + `open_labels.xlsx` (columns: file name, timestamp, "violation / no violation"). **22 violation, 20 no violation.** Violation **types are not given**; the team defines them.
- H.264, 464x848 (portrait), ~30 fps (e.g. 29.92), duration roughly 26-143 s (X-14 is 142.5 s, 4,273 frames), ~2-29 MB each.
- Violation timestamps (seconds): X-1 22; X-2 10; 4 -> 57; 11 -> 18; 13 -> 47; 15 -> 15; 17 -> 7; 18 -> 20; 20 -> 5; 22 -> 14; 24 -> 8; 26 -> 9; 28 -> 7; 30 -> 13; 32 -> 5; 33 -> 6; 34 -> 13; 38 -> 33; 40 -> 17; 44 -> 16; 46 -> 11; 47 -> "1 minute 8 seconds" (68).
- No violation: 3, 5, 8, 10, 12, 14, 16, 19, 21, 23, 25, 27, 29, 31, 35, 37, 39, 43, 45, 48.
- **Gotchas:** videos 4 and 47 are byte-identical (same md5) but labelled with different timecodes (57 s and 68 s): two violations in one video, or label noise. Videos 5 and 48 are identical too (both "no violation"). Never put duplicates into train and validation at the same time. File names: `X-1` and `X-2` use a Latin X, the rest use Cyrillic "Kh" (`#U0425` in the zip listing); match by the number in the name (the eval script does).
- Scene (4 frames viewed): office room, camera above and to the side, cashier at a desk with a laptop and other people in frame. Violation types were NOT derived from these frames. **First task at the event:** watch the videos around the labelled seconds, cluster violations into types, then map each type to real NBRK / adilet.zan.kz norms.

---

## 5. What was verified in the sandbox (the rest is untested)

- Label parsing: 42 rows, 22 violations; `parse_ts("1минута 8 секунда") == 68`.
- OpenCV `cap.set(CAP_PROP_POS_MSEC, 22000)` then `read()` on X-1 returned a frame at 22,000 ms; JPEG at quality 85 was ~58 KB (base64 ~78 KB), so a result with 3 frames per violation is small.
- Decode + 2 fps sampling of X-14: 7.0 s on one core.
- Python files compile (`py_compile`). FastAPI, Postgres, Docker were not available in the sandbox.

---

## 6. Hardware and hosting decisions

**CPU only.** Use light detectors / classifiers (nano/mobile class) in **ONNX Runtime** or **OpenVINO** (works well on Intel). Large vision-language models on every frame will not fit the time budget on CPU; at most on a few candidate frames after measuring. If PyTorch is needed in the image, use the CPU wheel: `pip install torch --index-url https://download.pytorch.org/whl/cpu`.

**Alfia's MacBook.** If it is Apple Silicon, PyTorch can use `mps` natively, but **not inside Docker** (Docker on Mac runs a Linux VM). Fine for experiments/training on the Mac; the **service must run on an Intel/Windows laptop**, and inference speed must be re-measured on CPU. Images built on Apple Silicon are arm64 and will not run on Intel (amd64) unless built multi-arch; build the image on the machine that will host it. Weights are portable; pin library versions. In the model code the device must be `cpu`.

**Where to host.** On the laptop with the best CPU and the most stable internet. Windows/Docker resources: create `C:\Users\<name>\.wslconfig`
```
[wsl2]
memory=8GB
processors=6
```
(numbers according to the machine; do not give Docker all RAM), then `wsl --shutdown` and restart Docker Desktop. Power settings: never sleep while plugged in. Do not restart the service while the jury is testing. If the Docker slow-download problem recurs (weak 4G), download heavy images/wheels beforehand.

**Public URL (mandatory).** Options (free-tier terms must be checked on the vendors' sites; I could not verify them):
1. **Cloudflare quick tunnel:** install `cloudflared` (e.g. `winget install --id Cloudflare.cloudflared`, or download from Cloudflare), run `cloudflared tunnel --url http://localhost:8000`. It prints a random `https://....trycloudflare.com` URL that **changes every restart** (bad for a URL you hand to the jury). A named tunnel needs a domain on Cloudflare.
2. **ngrok:** `ngrok http 8000` after adding your authtoken; a free static domain may be available (check current ngrok docs for the exact flag).
3. **Rented server** where you run your own container (it is your own service, not a cloud AI API), but ask the organizers first.
TLS is provided by the tunnel, so the public URL is `https`.

**Google Colab / Kaggle (the chat said "Colab/соуп"; "соуп" unclear, probably Kaggle).**
- For **serving the jury (inference): not acceptable.** Test videos must not be passed to third parties; Colab is Google infrastructure; sessions die and there is no stable public address.
- For **training** on the training videos: **gray zone.** The ban is about cloud AI services/APIs, and Colab is a compute environment, but the data may be used only within the hackathon and uploading to Drive is external storage. **Do not upload videos to any cloud until the organizers answer.** This is my reading, not an official answer.
- Message to send to the organizers (Telegram @nu_datasci), Russian:
> Добрый день! Уточните, пожалуйста: 1) можно ли обучать модель на тренировочных видео в Google Colab/Kaggle (загрузка видео в облачную среду)? 2) можно ли арендовать сервер/GPU-хост и запускать на нём собственный контейнер с моделями для публичного URL? Модели при этом выполняются внутри нашего сервиса, облачные AI-API не используются.

**Licenses.** Check every model's license (commercial use). For example, Ultralytics YOLO is distributed under AGPL-3.0 (verify before choosing); large VLMs have varied licenses.

---

## 7. Build-ready code (`api_skeleton`)

File tree:
```
api_skeleton/
  main.py                  FastAPI app: jury API, UI routes, health, static UI
  db.py                    Postgres access (jobs table)
  requirements.txt
  Dockerfile
  docker-compose.yml       db (postgres:16-alpine) + api
  .dockerignore
  .env.example             API_KEY, WORKERS
  model_service.py.template  rename to model_service.py when the model is ready
  static/index.html        minimal working UI (Aidyn can replace it)
  models/                  put weights here (mounted read-only into the container)
  tools/test_client.py     one-video smoke test of the jury API
  tools/load_test.py       N videos at once (must all finish < 300 s)
  tools/eval_labels.py     accuracy + timecode check against open_labels.xlsx
```
Status: syntax-checked only (label parsing in `eval_labels.py` was executed). The Docker build, compose startup, UI and API were **not run**: run them and report errors.

### main.py
```python
import os, uuid, base64, logging, importlib.util
from concurrent.futures import ThreadPoolExecutor

import cv2
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.staticfiles import StaticFiles

import db

log = logging.getLogger("uvicorn.error")

API_KEY = os.environ.get("API_KEY", "change-me")         # set via .env / docker compose
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")
WORKERS = int(os.environ.get("WORKERS", "1"))            # parallel analyses (see queue math in the doc)
MAX_BYTES = 200 * 1024 * 1024

app = FastAPI(title="Cash discipline video analyzer")
POOL = ThreadPoolExecutor(max_workers=WORKERS)

# The real model lives in model_service.py (copy of model_service.py.template + notebook code).
# If the file exists, import errors are NOT swallowed (a broken model must fail loudly).
if importlib.util.find_spec("model_service") is not None:
    from model_service import analyze_video
    MODEL_LOADED = True
else:
    MODEL_LOADED = False

    def analyze_video(path):
        log.warning("model_service.py not found: returning STUB result (no_violation)")
        return []


@app.on_event("startup")
def startup():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db.init_db()


def check_key(x_api_key):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


def frame_b64(video_path, t_sec):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode() if ok else None


def run_job(job_id, path):
    try:
        violations = []
        for v in analyze_video(path):
            t = float(v["timecode_sec"])
            img = frame_b64(path, t)
            violations.append({
                "type": v["type"],
                "timecode_sec": t,
                "description": v["description"],
                "rule": v.get("rule", ""),   # extra field, not in the official schema (see doc)
                "evidence_frames": [{"timestamp_sec": t, "image_base64": img}] if img else [],
            })
        db.finish_job(job_id, "done", {"verdict": "violation" if violations else "no_violation",
                                       "violations": violations})
    except Exception as e:
        log.exception("job %s failed", job_id)
        db.finish_job(job_id, "failed", {"error": str(e)})
    finally:
        if os.path.exists(path):
            os.remove(path)                               # jury videos are not kept after processing


async def submit(file: UploadFile):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    job_id = uuid.uuid4().hex[:8]
    path = os.path.join(UPLOAD_DIR, f"{job_id}.mov")
    with open(path, "wb") as f:
        f.write(data)
    db.create_job(job_id)
    POOL.submit(run_job, job_id, path)
    return job_id


def fetch(job_id):
    row = db.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    status, result = row
    return {"job_id": job_id, "status": status, **(result or {})}


# ---- Jury API (key required) -------------------------------------------------
@app.post("/api/v1/analyze")
async def analyze(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    return {"job_id": await submit(file)}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, x_api_key: str = Header(None)):
    check_key(x_api_key)
    return fetch(job_id)


# ---- Browser UI routes (no key; the UI is served from this same app) ---------
@app.post("/ui/api/analyze")
async def ui_analyze(file: UploadFile = File(...)):
    return {"job_id": await submit(file)}


@app.get("/ui/api/jobs/{job_id}")
def ui_job(job_id: str):
    return fetch(job_id)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": MODEL_LOADED, "workers": WORKERS}


# Must stay LAST: serves static/index.html at "/"
if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="ui")
```

### db.py
```python
import os, time
import psycopg
from psycopg.types.json import Jsonb

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://app:app@db:5432/app")


def _conn():
    return psycopg.connect(DATABASE_URL, autocommit=True)


def init_db(retries=30):
    """Создаёт таблицу; ждёт, пока контейнер БД поднимется."""
    for _ in range(retries):
        try:
            with _conn() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result JSONB,
                    created_at TIMESTAMPTZ DEFAULT now())""")
                # задачи, оставшиеся 'processing' после перезапуска, помечаем как failed
                c.execute("UPDATE jobs SET status='failed', result=%s WHERE status='processing'",
                          (Jsonb({"error": "server restarted"}),))
            return
        except psycopg.OperationalError:
            time.sleep(1)
    raise RuntimeError("database is not available")


def create_job(job_id):
    with _conn() as c:
        c.execute("INSERT INTO jobs (job_id, status) VALUES (%s, 'processing')", (job_id,))


def finish_job(job_id, status, result):
    with _conn() as c:
        c.execute("UPDATE jobs SET status=%s, result=%s WHERE job_id=%s",
                  (status, Jsonb(result), job_id))


def get_job(job_id):
    with _conn() as c:
        return c.execute("SELECT status, result FROM jobs WHERE job_id=%s", (job_id,)).fetchone()
```

### requirements.txt
```
fastapi
uvicorn
python-multipart
aiofiles
opencv-python-headless
psycopg[binary]
```

### Dockerfile
```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 3s
      timeout: 3s
      retries: 20

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      API_KEY: ${API_KEY:-change-me}
      DATABASE_URL: postgresql://app:app@db:5432/app
      UPLOAD_DIR: /data/uploads
      WORKERS: ${WORKERS:-1}
    volumes:
      - uploads:/data/uploads
      - ./models:/app/models:ro
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
  uploads:
```

### .dockerignore
```
.git
__pycache__
*.mov
*.pyc
```

### .env.example
```
API_KEY=change-me-to-a-long-random-string
WORKERS=1
```

### model_service.py.template
```python
"""Template. Copy to model_service.py once the notebook inference code is ready.
Contract: analyze_video(path) -> list of {"type", "timecode_sec", "description", "rule"}; [] = no violation.
The model is loaded ONCE at import time. No internet access, no cloud APIs."""
import os, time
import cv2
# import onnxruntime as ort

MODEL_DIR = os.environ.get("MODEL_DIR", "models")
SAMPLE_FPS = 2            # frames per second that are analysed
JOB_BUDGET_SEC = 240      # stop and return a partial result before the 5-minute jury limit

# SESSION = ort.InferenceSession(os.path.join(MODEL_DIR, "model.onnx"),
#                                providers=["CPUExecutionProvider"])   # loaded once


def iter_frames(path, sample_fps=SAMPLE_FPS):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / sample_fps)))
    i = 0
    while True:
        if not cap.grab():          # grab() is cheap; retrieve() only on sampled frames
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                yield i / fps, frame
        i += 1
    cap.release()


def analyze_video(path):
    start = time.time()
    found = []
    for t, frame in iter_frames(path):
        if time.time() - start > JOB_BUDGET_SEC:
            break
        # TODO: run the model on `frame`; when an event is detected:
        # found.append({"type": "...", "timecode_sec": t, "description": "...", "rule": "..."})
        pass
    return found
```

### static/index.html
```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Cash discipline video check</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem}
img{max-width:240px;margin:4px}.v{border:1px solid #888;padding:12px;margin:12px 0}</style></head>
<body><h1>Cash discipline video check</h1>
<input type="file" id="f" accept=".mov,video/quicktime"><button id="go">Analyze</button>
<p id="status"></p><div id="out"></div>
<script>
const $ = id => document.getElementById(id);
$("go").onclick = async () => {
  const file = $("f").files[0];
  if (!file) { $("status").textContent = "Choose a .mov file"; return; }
  $("out").textContent = ""; $("status").textContent = "Uploading...";
  const fd = new FormData(); fd.append("file", file);
  const r = await fetch("/ui/api/analyze", { method: "POST", body: fd });
  if (!r.ok) { $("status").textContent = "Upload failed: " + r.status; return; }
  const { job_id } = await r.json(); $("status").textContent = "Processing...";
  while (true) {
    await new Promise(s => setTimeout(s, 2000));
    const j = await (await fetch("/ui/api/jobs/" + job_id)).json();
    if (j.status === "processing") continue;
    if (j.status === "failed") { $("status").textContent = "Failed: " + (j.error || ""); return; }
    show(j); return;
  }
};
function show(j) {
  $("status").textContent = j.verdict === "violation" ? "Signs of possible violations found" : "No violation detected";
  for (const v of j.violations || []) {
    const d = document.createElement("div"); d.className = "v";
    const h = document.createElement("b"); h.textContent = v.type + " @ " + v.timecode_sec + " s";
    const p = document.createElement("p"); p.textContent = v.description;
    const r = document.createElement("p"); r.textContent = "Rule: " + (v.rule || "-");
    d.append(h, p, r);
    for (const f of v.evidence_frames) { const i = document.createElement("img"); i.src = "data:image/jpeg;base64," + f.image_base64; d.append(i); }
    $("out").append(d);
  }
}
</script></body></html>
```

### tools/test_client.py
```python
"""Smoke test of the jury API. Usage: python test_client.py BASE_URL API_KEY path/to/video.mov
Requires: pip install requests"""
import sys, time, base64
import requests

base, key, path = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
H = {"X-API-Key": key}
t0 = time.time()
with open(path, "rb") as f:
    r = requests.post(f"{base}/api/v1/analyze", headers=H, files={"file": f})
r.raise_for_status()
job = r.json()["job_id"]
print("job_id:", job)
while True:
    j = requests.get(f"{base}/api/v1/jobs/{job}", headers=H).json()
    if j["status"] != "processing":
        break
    time.sleep(2)
print("status:", j["status"], "| elapsed:", round(time.time() - t0, 1), "s")
print("verdict:", j.get("verdict"), "| error:", j.get("error"))
for v in j.get("violations", []):
    print("-", v["type"], v["timecode_sec"], v["description"])
    for k, fr in enumerate(v["evidence_frames"]):
        with open(f"evidence_{job}_{k}.jpg", "wb") as out:
            out.write(base64.b64decode(fr["image_base64"]))
```

### tools/load_test.py
```python
"""Simulates the jury submitting N videos at once. Every one must finish in < 300 s.
Usage: python load_test.py BASE_URL API_KEY video1.mov video2.mov ...
Requires: pip install requests"""
import sys, time
from concurrent.futures import ThreadPoolExecutor
import requests

base, key, paths = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3:]
H = {"X-API-Key": key}


def one(path):
    t0 = time.time()
    with open(path, "rb") as f:
        job = requests.post(f"{base}/api/v1/analyze", headers=H, files={"file": f}).json()["job_id"]
    while True:
        j = requests.get(f"{base}/api/v1/jobs/{job}", headers=H).json()
        if j["status"] != "processing":
            return path, j["status"], j.get("verdict"), round(time.time() - t0, 1)
        time.sleep(2)


with ThreadPoolExecutor(max_workers=len(paths)) as ex:
    results = list(ex.map(one, paths))
for r in results:
    print(r)
worst = max(r[3] for r in results)
print("WORST:", worst, "s ->", "OK (< 300 s)" if worst < 300 else "TOO SLOW")
```

### tools/eval_labels.py
```python
"""Runs every labelled video through the API and compares with open_labels.xlsx.
Usage: python eval_labels.py BASE_URL API_KEY path/to/open  [tolerance_sec]
(path/to/open contains videos/ and open_labels.xlsx). Requires: pip install requests openpyxl"""
import sys, re, glob, os, time


def parse_ts(s):
    """'22 секунда' -> 22.0 ; '1минута 8 секунда' -> 68.0 ; empty -> None"""
    if not s:
        return None
    m = re.search(r"(\d+)\s*минут", s)
    sec = re.search(r"(\d+)\s*секунд", s)
    return (int(m.group(1)) * 60 if m else 0) + (int(sec.group(1)) if sec else 0)


def load_labels(xlsx):
    from openpyxl import load_workbook
    ws = load_workbook(xlsx, read_only=True).active
    out = {}
    for row in list(ws.iter_rows(values_only=True))[1:]:
        name, ts, verdict = row[0], row[1], row[2]
        if not name:
            continue
        num = int(re.search(r"(\d+)", str(name)).group(1))     # robust to Latin X / Cyrillic Х
        out[num] = ("violation" if str(verdict).strip() == "нарушение" else "no_violation", parse_ts(ts))
    return out


def main():
    import requests
    base, key, root = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    tol = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
    H = {"X-API-Key": key}
    labels = load_labels(os.path.join(root, "open_labels.xlsx"))
    files = {int(re.search(r"(\d+)", os.path.basename(p)).group(1)): p
             for p in glob.glob(os.path.join(root, "videos", "*.mov"))}
    ok = 0; tl = 0; tl_total = 0; slowest = 0
    for num, (true_verdict, true_ts) in sorted(labels.items()):
        if num not in files:
            continue
        t0 = time.time()
        with open(files[num], "rb") as f:
            job = requests.post(f"{base}/api/v1/analyze", headers=H, files={"file": f}).json()["job_id"]
        while True:
            j = requests.get(f"{base}/api/v1/jobs/{job}", headers=H).json()
            if j["status"] != "processing":
                break
            time.sleep(2)
        dt = time.time() - t0; slowest = max(slowest, dt)
        pred = j.get("verdict")
        ok += pred == true_verdict
        near = None
        if true_verdict == "violation" and pred == "violation":
            near = min(abs(v["timecode_sec"] - true_ts) for v in j["violations"]) <= tol
            tl_total += 1; tl += bool(near)
        print(f"video {num}: true={true_verdict} pred={pred} time_ok={near} {dt:.0f}s")
    print(f"verdict accuracy: {ok}/{len(labels)}; timecode within {tol}s: {tl}/{tl_total}; slowest: {slowest:.0f}s")


if __name__ == "__main__":
    main()
```

---

## 8. Build, run, test: exact commands (Windows PowerShell)

```powershell
cd C:\dev\cashier-api
copy .env.example .env                 # then edit .env: API_KEY=<long random string>, WORKERS=1
docker compose up --build              # first build is slow on a weak connection (pip cache mount helps later)
```
Open http://localhost:8000 (UI) and http://localhost:8000/health (expect `{"status":"ok","model_loaded":false,"workers":1}` until a model is plugged in).

Smoke test with curl (use `curl.exe` in PowerShell, plain `curl` is an alias for something else):
```powershell
curl.exe -X POST http://localhost:8000/api/v1/analyze -H "X-API-Key: <key>" -F "file=@video.mov"
curl.exe http://localhost:8000/api/v1/jobs/<job_id> -H "X-API-Key: <key>"
curl.exe -i http://localhost:8000/api/v1/jobs/<job_id>          # no key -> HTTP 401
```
Python tools (on the host, `pip install requests openpyxl`):
```powershell
python tools\test_client.py http://localhost:8000 <key> C:\data\open\videos\X-1.mov
python tools\load_test.py   http://localhost:8000 <key> v1.mov v2.mov v3.mov v4.mov v5.mov
python tools\eval_labels.py http://localhost:8000 <key> C:\data\open 3
```
Useful Docker/Compose commands: `docker compose up --build -d` (background), `docker compose logs -f api`, `docker compose restart api`, `docker compose down` (keeps volumes), `docker compose down -v` (also wipes the database and uploads).

### Troubleshooting table
| Symptom | Likely cause / fix |
|---|---|
| `the Dockerfile cannot be empty` | File not saved (Ctrl+S), wrong name (`Dockerfile.txt`), or UTF-16 encoding. Check `Get-Content Dockerfile`. Recreate with `Set-Content -Encoding ascii`. |
| `pip install` extremely slow | Weak network (was ~24 kB/s on 4G). Switch network, do not switch mid-download, keep the pip cache mount, pre-download heavy packages. |
| API container exits at start / DB errors | DB not ready yet (compose healthcheck handles it); look at `docker compose logs api db`. |
| `models/` bind mount problems on Windows | Create the `models` folder before `up`; keep the project outside OneDrive. |
| `model_loaded: false` | `model_service.py` not present in the image (rename the template, rebuild). |
| Jobs stuck in `processing` | Worker crashed or the model is too slow; check logs; stale jobs are failed on restart. |
| Public URL works for you but not for others | Tunnel restarted (new random URL), laptop asleep, or firewall; test from mobile data. |
| Image built on a Mac fails on Intel | arm64 vs amd64; build on the host machine. |

---

## 9. Notebook-to-service workflow (Alfia trains in Jupyter, Shah integrates)

**What Alfia should deliver** (message for her, in Russian, copy as is):
> Чтобы я быстро встроил модель в сервис, сделай так: 1) В конце ноутбука отдельная ячейка с функцией `analyze_video(path)`: принимает путь к видео, возвращает список словарей `{type, timecode_sec, description, rule}` (пустой список = нарушений нет), не зависит от переменных из ячеек обучения. 2) Обучение и инференс в разных ячейках, в инференсе нет `!pip` и `%` команд. 3) Веса сохранять в файл (лучше экспорт в ONNX, иначе `state_dict`, не весь объект модели) и класть в `models/`; пути относительные. 4) Ничего не скачивается при запуске (никаких `from_pretrained` из интернета), всё из локальных файлов. 5) Пороги, частоту выборки кадров и список типов нарушений вынести в отдельную ячейку-конфиг. 6) Прогнать на самом длинном видео (Х-14) и написать, сколько секунд это заняло на CPU. 7) В конце списком: библиотеки с точными версиями и лицензия каждой модели. Зафиксируй seed.

**What Shah does with the notebook:**
1. Run it inside Docker Jupyter (same Linux/Intel/CPU environment as the service):
   `docker run -p 8888:8888 -v ${PWD}:/home/jovyan/work jupyter/scipy-notebook`, open the printed `http://127.0.0.1:8888/lab?token=...` link; the project folder appears as `work/`. Install missing libraries in the first cell and record them in `requirements.txt`. (The newer official images live at `quay.io/jupyter/scipy-notebook`; the Docker Hub tag is stale but works.)
2. Verify: run her function on 3-5 labelled videos (e.g. X-1 -> violation near 22 s, video 3 -> none) and confirm the same answers she saw on the Mac.
3. Extract inference into a module: `jupyter nbconvert --to script notebook.ipynb`, then copy only the inference cells into `model_service.py` (start from `model_service.py.template`: ONNX session loaded once, `iter_frames`, the deadline guard).
4. Add libraries to `requirements.txt`, weights to `models/`, `docker compose up --build`, check `/health` shows `model_loaded: true`.
5. Run `tools/eval_labels.py` and `tools/load_test.py`; report the slowest time to Alfia. Over ~90 s per video means a lighter model or fewer sampled frames.

**Watch out for:** device must be `cpu` (no `mps`/`cuda`), thread counts when `WORKERS > 1`, Apple-Silicon-only wheels, model licenses, fixed random seeds, and the extra `rule` field (see 3.3).

---

## 10. What to hand the jury (and a template for "run and usage instructions")

Required by the brief: (1) working UI address, (2) API address, (3) API key, (4) run/usage instructions, plus Alfia's documents (architecture and models; regulatory sources and rule-to-video mapping; violation types list; limitations and known errors).

Template for the instructions document (fill in `[...]`):
```
# [Service name]: run and usage

## Public addresses
UI:  https://[public-host]/
API: https://[public-host]/api/v1
API key (header X-API-Key): [key]

## Use the UI
Open the UI, choose a .mov file (10-145 s, ~29 MB), press Analyze, wait for the status,
then read the verdict, violation types, timecodes, descriptions, rules/sources and evidence frames.

## Use the API
curl -X POST https://[public-host]/api/v1/analyze -H "X-API-Key: [key]" -F "file=@video.mov"   -> {"job_id": "..."}
curl https://[public-host]/api/v1/jobs/[job_id] -H "X-API-Key: [key]"   -> status processing | done | failed (+ result)
Result fields: verdict (violation | no_violation), violations[].type, timecode_sec, description, evidence_frames[].timestamp_sec/image_base64

## Run locally (no internet needed after the first build)
1. Install Docker Desktop.  2. Copy .env.example to .env and set API_KEY.
3. docker compose up --build   4. Open http://localhost:8000
Models are in ./models and run locally on CPU; no cloud AI services are used.

## Limits
Processing target: [N] s per video. Jobs are stored in Postgres; uploaded videos are deleted after processing.
```

---

## 11. Docker: terms and history

- **Image** = template; **container** = running instance; **Dockerfile** = build recipe; **Docker Hub** = image registry; **Compose** = several containers described in one file; **`-p 8000:8000`** publishes a container port; **`-v`** / **volume** = persistent or shared folder (`pgdata`, `uploads`, `./models`); **`0.0.0.0`** = listen address inside the container (otherwise the service is not reachable from outside); **BuildKit cache mount** = pip cache reused between builds (do not combine with `--no-cache-dir`); **WSL 2** = Linux subsystem Docker Desktop uses on Windows; **healthcheck** = readiness probe (used so the API waits for Postgres).
- Core commands: `docker pull`, `docker images`, `docker ps [-a]`, `docker build -t name .`, `docker run -p 8000:8000 name`, `docker logs <id>`, `docker stop`, `docker rm`, `docker compose up --build`, `docker compose down`.
- History: `hello-world`, `python:3.11-slim` and `jupyter/scipy-notebook` pulled fine. First error "Dockerfile cannot be empty" (file not saved), then fixed; `docker build` works. A build was extremely slow because of 4G (pip ~24 kB/s while fetching pandas/scikit-learn); the solution was a better network and cached layers. Useful VS Code extensions: Docker, Dev Containers.
- Tips: shared GitHub repo with Dockerfile/requirements; `.dockerignore`; never bake the dataset into an image (mount it); fallback `python -m venv` if Docker misbehaves.

---

## 12. Workshop lessons (How to Win the Datathon, team Richards)

1. Judges check the list: turn the brief into a checklist in hour 1 and show every box ticked on screen. Complete beats impressive.
2. With an MVP that covers everything and hours left: go deeper, not wider (harden the demo, measure, sharpen explanations, record a backup video, finish the README, rehearse).
3. Simple beats full: one clear flow, nothing the user did not ask for.
4. Show the work, not the stack: screenshot + number + one plain sentence; for a niche technique name it, cite the paper, show what it fixed.
5. Prepare in advance: slide template, environment, code skeleton (if allowed), front end only if needed.
6. Analyze the jury, not only the case. Pick one path and adapt. Stand out with results, not tech (last time a team built its own model and lost to teams using a ready one).
7. **"Deploy is a bonus" does NOT apply to this case: a public URL and API are mandatory.**
8. On stage show what works (data in -> model runs -> result + why); answer honestly about weak spots but do not volunteer them.
9. The pitch can be very short (workshop said 2 min; this case's finalists get 5 min + 2 min Q&A). Rehearse with a timer; do not explain the problem to the jury; plan one memorable moment.

---

## 13. Existing artifacts, open items, risks, decisions

**Already made:**
- Pitch template deck (7 slides, violet-black "game log" style, hotbar progress): https://claude.ai/artifact/Sr6p3x9kgNSSQDtNnKk96Y (layout was not visually verified; adapt content to this case: local models, rule grounding).
- README template (`README.md`: result first, problem, what we built, explanations, method, brief checklist, how to run, structure, limitations, team).
- `api_skeleton` (section 7).

**Not done yet:** a report template, Alfia's documents, the run/usage instructions, the real UI (Aidyn), the model, the public tunnel/URL, answers from the organizers.

**Top risks:** (1) CPU inference too slow for 5 jury videos at once; (2) public URL unstable (random tunnel URL, laptop sleep, restart during checking); (3) invented/unsupported regulatory references (15 points); (4) missed violations or false positives (the bank penalizes both, misses most); (5) test video from a different camera angle (robustness: avoid brittle pixel-position rules); (6) model licenses; (7) uploading videos to cloud services before the organizers confirm it is allowed; (8) duplicate/ambiguous labels (videos 4/47, 5/48).

**Decisions made:** FastAPI + Postgres in Docker Compose; two-step async API exactly as in the brief; jury routes with `X-API-Key`, UI routes without key; ONNX/CPU inference loaded once; partial results over timeouts; service hosted on an Intel Windows laptop behind a tunnel; Colab/Kaggle only maybe for training and only after organizers confirm.

**Open questions:** Alfia's Mac chip; organizers' answers (Colab for training, rented server); which tunnel gives a stable URL; per-video inference time on the team's CPUs; which violation types exist in the data; which NBRK / adilet.zan.kz clauses map to them.

---

## 14. Prompt for the next AI

> You are helping Shah (Windows 11, Intel CPU, Docker Desktop, VS Code; team of 3 at Datathon '26, ForteBank case: detect cash-desk discipline violations in videos; fully local models, CPU only, mandatory public URL, jury API with `X-API-Key`, two-step async job API, 5-minute limit per video). His role: server, API, Postgres container, public address and key, run instructions, and integrating the model that Alfiya trains in a Jupyter notebook. Everything above is the context and the code is in section 7 (untested beyond syntax). My next task: > My next task: act as the integration lead for Shah's part and take the project from "skeleton" to "working end-to-end service, ready to give to the jury". Work in this order, one step at a time, and ask me only for what is missing:
>
> 1. **Get the stack running.** I will run `docker compose up --build` from the `api_skeleton` folder and paste the output. Diagnose and fix errors. Success = `http://localhost:8000/health` returns `{"status":"ok", ...}` and the UI opens.
> 2. **Smoke-test the API** with `tools/test_client.py` and curl: 401 without key, `job_id` with key, `processing` -> `done`, 404 for an unknown id. With no model plugged in, `no_violation` is the expected result.
> 3. **Integrate Alfia's notebook** (she trains in Jupyter on a Mac) into `model_service.py` following section 9. Contract she must meet: a function `analyze_video(path)` returning a list of `{type, timecode_sec, description, rule}`; weights in `models/` (ONNX preferred); no downloads at runtime; config cell with thresholds and sampling rate; pinned library versions; license of each model; inference time on the longest video (X-14) on CPU.
> 4. **Integrate Aidyn's UI.** Contract he must meet: static files only (an `index.html` plus assets, or a built `dist/`), no build step on the server, no external CDN/fonts (bundle everything locally; the service must work without internet). He copies them into `static/`. The UI calls `POST /ui/api/analyze` (multipart field `file`, returns `{job_id}`), polls `GET /ui/api/jobs/{job_id}` every ~2 s, and handles states `processing`, `failed` (shows `error`) and `done`. For `done` it shows the verdict ("No violation detected" / "Signs of possible violations detected") and, for each item in `violations`: `type`, `timecode_sec`, `description`, `rule`, and the `evidence_frames` rendered from `image_base64` as `data:image/jpeg;base64,...`. ForteBank-style visual design; Russian or English texts. Never insert API text with `innerHTML` (use `textContent`). The existing `static/index.html` is a working baseline he can restyle.
> 5. **Measure and harden.** Run `tools/eval_labels.py` (verdict accuracy and timecode hit rate on the 42 labelled videos) and `tools/load_test.py` with 5 videos at once (every video must finish in under 300 s). Tune `WORKERS`, frame sampling rate and thread counts using the queue math in section 3.6. If a video takes over ~90 s, tell Alfia to use a lighter model or fewer frames.
> 6. **Go public.** Set up a tunnel with the most stable URL available (section 6), test the public URL from a different network (phone on mobile data), generate the API key, and keep the laptop awake and plugged in.
> 7. **Prepare the handover** for the jury: UI URL, API base URL, API key, and the run/usage instructions (fill the template from section 10). Alfia writes the architecture, regulatory sources, violation types and limitations documents; remind us about them.
>
> **Definition of done:** (a) UI works end to end on the public URL; (b) the jury API works with `X-API-Key` and the exact schema from section 3.3; (c) 5 simultaneous videos all return in under 300 s; (d) models run locally on CPU with no internet and no cloud AI calls; (e) the service survives a restart; (f) jury handover is ready.
>
> **Rules for you:** give exact copy-paste commands (Windows PowerShell, `curl.exe`), say clearly what is untested, never invent regulatory references or model licenses, and if I paste an error, find the root cause before suggesting changes. Do not ask me what my task is: it is the list above. Reply in English (actually everything should be in English not in Russian), give copy-paste-ready code if needed (but it would be better if you could run everything yourself) and exact commands, and say clearly what is untested.
