"""Offline CPU video service. Run a single uvicorn process per database."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hmac
import importlib.util
import logging
import math
import os
import json
from pathlib import Path
import threading
import time
import uuid
from typing import Annotated, Literal

import cv2
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

import db

log = logging.getLogger("uvicorn.error")
ROOT = Path(__file__).resolve().parent
API_KEY = os.environ.get("API_KEY", "change-me")
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(ROOT / "uploads")))
WORKERS = int(os.environ.get("WORKERS", "1"))
MAX_BYTES = 200 * 1024 * 1024
INCLUDE_RULE = os.environ.get("INCLUDE_RULE", "true").lower() == "true"
JOB_TIMEOUT_SEC = float(os.environ.get("JOB_TIMEOUT_SEC", "270"))

if importlib.util.find_spec("model_service") is not None:
    from model_service import analyze_video
    MODEL_LOADED = True
else:
    MODEL_LOADED = False

    def analyze_video(path):
        return []


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Evidence(ContractModel):
    timestamp_sec: Seconds
    image_base64: str


class Violation(ContractModel):
    type: str
    timecode_sec: Seconds
    description: str
    evidence_frames: list[Evidence] = Field(min_length=1, max_length=3)
    rule: str | None = None


class Submitted(ContractModel):
    job_id: str


class Processing(Submitted):
    status: Literal["processing"]


class Done(Submitted):
    status: Literal["done"]
    verdict: Literal["violation", "no_violation"]
    violations: list[Violation]


class Failed(Submitted):
    status: Literal["failed"]
    error: str


JobResponse = Annotated[Processing | Done | Failed, Field(discriminator="status")]


@asynccontextmanager
async def lifespan(app):
    if not API_KEY or WORKERS < 1 or not math.isfinite(JOB_TIMEOUT_SEC) or JOB_TIMEOUT_SEC <= 0:
        raise RuntimeError("API_KEY must be nonempty; WORKERS and JOB_TIMEOUT_SEC must be positive")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await run_in_threadpool(db.init_db)
    # This directory belongs exclusively to this service; discard interrupted uploads.
    for path in UPLOAD_DIR.glob("*.mov"):
        path.unlink(missing_ok=True)
    app.state.pool = ThreadPoolExecutor(max_workers=WORKERS)
    if not MODEL_LOADED:
        log.warning("model_service.py absent: stub returns no_violation")
    try:
        yield
    finally:
        await run_in_threadpool(app.state.pool.shutdown, wait=True)


app = FastAPI(title="Cash discipline video analyzer", lifespan=lifespan)


def check_key(x_api_key: str | None = Header(None)):
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), API_KEY.encode()):
        raise HTTPException(status_code=401, detail="invalid api key")


@dataclass
class JobControl:
    job_id: str
    path: Path
    submitted: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)
    finished: bool = False
    timer: threading.Timer | None = None
    future: object = None

    def finish(self, status, result):
        with self.lock:
            if self.finished:
                return False
            duration = time.monotonic() - self.submitted
            if duration >= JOB_TIMEOUT_SEC:
                status, result = "failed", {"error": "job timeout exceeded"}
            db.finish_job(self.job_id, status, result)
            self.finished = True
            if self.timer:
                self.timer.cancel()
            # Log only these fields, never model exceptions, files, keys or frames.
            log.info(json.dumps({"job_id": self.job_id, "duration_sec": round(duration, 3),
                                 "verdict": result.get("verdict", "failed")}))
            return True

    def expire(self):
        try:
            self.finish("failed", {"error": "job timeout exceeded"})
        except Exception:
            # Retry if the database was temporarily unavailable at the deadline.
            self.timer = threading.Timer(1, self.expire)
            self.timer.daemon = True
            self.timer.start()
            return
        if self.future and self.future.cancel():
            self.path.unlink(missing_ok=True)


def frame_b64(video_path, t_sec):
    cap = cv2.VideoCapture(str(video_path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000)
        ok, frame = cap.read()
        fps = cap.get(cv2.CAP_PROP_FPS)
        fps = fps if math.isfinite(fps) and fps > 0 else 30.0
        timestamp = max(0.0, (cap.get(cv2.CAP_PROP_POS_FRAMES) - 1) / fps)
        if not ok:
            # Broken indexes and times beyond EOF: decode sequentially and retain
            # the nearest readable frame, including the first/last at the edges.
            cap.release()
            cap = cv2.VideoCapture(str(video_path))
            best, distance, index = None, float("inf"), 0
            while True:
                readable, candidate = cap.read()
                if not readable:
                    break
                candidate_time = index / fps
                if abs(candidate_time - t_sec) < distance:
                    best, timestamp = candidate, candidate_time
                    distance = abs(candidate_time - t_sec)
                index += 1
            if best is None:
                return None
            frame = best
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            return {"timestamp_sec": timestamp, "image_base64": base64.b64encode(buf).decode("ascii")}
        return None
    finally:
        cap.release()


def run_job(control):
    path = control.path
    try:
        if control.finished:
            return
        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened() or not cap.read()[0]:
                raise ValueError("video cannot be opened or has no decodable frames")
        finally:
            cap.release()
        violations = []
        for v in analyze_video(str(path)):
            if control.finished:
                return
            t = float(v["timecode_sec"])
            if not math.isfinite(t) or t < 0:
                raise ValueError("invalid model timecode")
            frame = frame_b64(path, t)
            if frame is None:
                raise ValueError("cannot extract evidence frame")
            violations.append(Violation(
                type=v["type"], timecode_sec=t, description=v["description"],
                rule=v.get("rule", ""), evidence_frames=[frame],
            ).model_dump())
        control.finish("done", {"verdict": "violation" if violations else "no_violation",
                                 "violations": violations})
    except Exception as exc:
        # Model exception text may contain video data or secrets.
        error = str(exc) if isinstance(exc, ValueError) and str(exc) in {
            "video cannot be opened or has no decodable frames", "invalid model timecode",
            "cannot extract evidence frame",
        } else f"analysis failed ({type(exc).__name__})"
        control.finish("failed", {"error": error})
    finally:
        path.unlink(missing_ok=True)


def _submit(source):
    job_id = uuid.uuid4().hex
    path = UPLOAD_DIR / f"{job_id}.mov"
    created = False
    try:
        size = 0
        with path.open("xb") as dest:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(status_code=413, detail="file too large")
                dest.write(chunk)
        if not size:
            raise HTTPException(status_code=400, detail="empty file")
        db.create_job(job_id)
        created = True
        control = JobControl(job_id, path)
        control.future = app.state.pool.submit(run_job, control)
        with control.lock:
            if not control.finished:
                control.timer = threading.Timer(JOB_TIMEOUT_SEC, control.expire)
                control.timer.daemon = True
                control.timer.start()
        return {"job_id": job_id}
    except Exception:
        path.unlink(missing_ok=True)
        if created:
            db.finish_job(job_id, "failed", {"error": "could not schedule analysis"})
        raise


async def submit(file):
    try:
        return await run_in_threadpool(_submit, file.file)
    finally:
        await file.close()


def fetch(job_id):
    row = db.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    status, result = row
    return {**(result or {}), "job_id": job_id, "status": status}


@app.post("/api/v1/analyze", response_model=Submitted, dependencies=[Depends(check_key)])
async def analyze(file: UploadFile = File(...)):
    return await submit(file)


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse, response_model_exclude_none=True,
         dependencies=[Depends(check_key)])
def get_job(job_id: str):
    result = fetch(job_id)
    if not INCLUDE_RULE and result["status"] == "done":
        result = {**result, "violations": [
            {key: value for key, value in v.items() if key != "rule"}
            for v in result["violations"]]}
    return result


@app.post("/ui/api/analyze", response_model=Submitted)
async def ui_analyze(file: UploadFile = File(...)):
    return await submit(file)


@app.get("/ui/api/jobs/{job_id}", response_model=JobResponse, response_model_exclude_none=True)
def ui_job(job_id: str):
    return fetch(job_id)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": MODEL_LOADED, "workers": WORKERS}


# The catch-all static mount must follow every API route.
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="ui")
