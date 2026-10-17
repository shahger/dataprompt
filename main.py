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
