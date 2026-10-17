"""Deterministic, local-only fixtures; production db is never imported by unit tests."""
from copy import deepcopy
import importlib
from pathlib import Path
import sys
import threading
import types

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "tiny.mov"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 24))
    assert writer.isOpened(), "OpenCV MOV writer unavailable"
    for n in range(10):
        writer.write(np.full((24, 32, 3), n * 20, dtype=np.uint8))
    writer.release()
    return path


@pytest.fixture
def service(monkeypatch, tmp_path):
    fake = types.ModuleType("db")
    rows = {}
    lock = threading.Lock()

    def init_db():
        with lock:
            for job_id, (status, _) in rows.items():
                if status == "processing":
                    rows[job_id] = ("failed", {"error": "server restarted"})

    def create_job(job_id):
        with lock:
            rows[job_id] = ("processing", None)

    def finish_job(job_id, status, result):
        with lock:
            if rows[job_id][0] == "processing":
                rows[job_id] = (status, deepcopy(result))

    def get_job(job_id):
        with lock:
            return deepcopy(rows.get(job_id))

    fake.init_db = init_db
    fake.create_job = create_job
    fake.finish_job = finish_job
    fake.get_job = get_job
    fake.rows = rows
    monkeypatch.setitem(sys.modules, "db", fake)
    monkeypatch.delitem(sys.modules, "main", raising=False)
    monkeypatch.setenv("API_KEY", "unit-test-key")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    module = importlib.import_module("main")
    monkeypatch.setattr(module, "analyze_video", lambda path: [])
    with TestClient(module.app) as client:
        yield module, client, fake
    sys.modules.pop("main", None)
