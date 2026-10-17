"""Opt-in real HTTP checks. These require the stub (no model_service.py)."""
import os
import time

import httpx
import pytest

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not (os.getenv("BASE_URL") and os.getenv("API_KEY")),
                                 reason="set BASE_URL and API_KEY for a running stack")]


def test_running_stack(video):
    headers = {"X-API-Key": os.environ["API_KEY"]}
    with httpx.Client(base_url=os.environ["BASE_URL"].rstrip("/"), timeout=30) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["model_loaded"] is False
        ui = client.get("/")
        assert ui.status_code == 200 and "text/html" in ui.headers["content-type"]
        assert client.get("/api/v1/jobs/unknown").status_code == 401
        assert client.get("/api/v1/jobs/unknown", headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.get("/api/v1/jobs/unknown", headers=headers).status_code == 404
        assert client.post("/api/v1/analyze", headers=headers).status_code == 422
        with video.open("rb") as stream:
            response = client.post("/api/v1/analyze", headers=headers, files={"file": ("tiny.mov", stream)})
        assert response.status_code == 200
        assert set(response.json()) == {"job_id"}
        job_id = response.json()["job_id"]
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            response = client.get("/api/v1/jobs/" + job_id, headers=headers)
            assert response.status_code == 200
            job = response.json()
            if job["status"] != "processing":
                break
            time.sleep(0.2)
        else:
            pytest.fail("stack exceeded 300 seconds")
        assert job == {"job_id": job_id, "status": "done", "verdict": "no_violation", "violations": []}
        assert client.get("/ui/api/jobs/" + job_id).json() == job
        with video.open("rb") as stream:
            assert client.post("/ui/api/analyze", files={"file": ("tiny.mov", stream)}).status_code == 200
