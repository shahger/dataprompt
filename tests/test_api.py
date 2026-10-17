import base64
import json
from pathlib import Path
import threading
import time

import cv2
import numpy as np
import pytest

HEADERS = {"X-API-Key": "unit-test-key"}


def upload(client, video, prefix="/api/v1", headers=HEADERS):
    with video.open("rb") as stream:
        return client.post(prefix + "/analyze", headers=headers, files={"file": ("tiny.mov", stream, "video/quicktime")})


def wait_job(client, job_id, prefix="/api/v1", headers=HEADERS):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(prefix + "/jobs/" + job_id, headers=headers)
        assert response.status_code == 200
        data = response.json()
        if data["status"] != "processing":
            return data
        time.sleep(0.01)
    pytest.fail("job did not finish within 5 seconds")


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_auth(service, video, headers):
    _, client, _ = service
    assert upload(client, video, headers=headers).status_code == 401
    assert client.get("/api/v1/jobs/unknown", headers=headers).status_code == 401
    assert client.post("/api/v1/analyze", headers=headers).status_code == 401


def test_health_ui_and_unknown(service):
    _, client, _ = service
    assert client.get("/health").json() == {"status": "ok", "model_loaded": False, "workers": 1, "demo_mode": False}
    assert "Контроль кассовой дисциплины" in client.get("/").text
    for prefix, headers in [("/api/v1", HEADERS), ("/ui/api", {})]:
        assert client.get(prefix + "/jobs/unknown", headers=headers).status_code == 404
        assert client.post(prefix + "/analyze", headers=headers).status_code == 422


def test_upload_rejections(service, monkeypatch):
    module, client, fake = service
    monkeypatch.setattr(module, "MAX_BYTES", 4)
    for content, expected in [(b"12345", 413), (b"", 400)]:
        assert client.post("/api/v1/analyze", headers=HEADERS, files={"file": ("a.mov", content)}).status_code == expected
    assert not fake.rows
    assert not list(module.UPLOAD_DIR.iterdir())


@pytest.mark.parametrize("prefix,headers", [("/api/v1", HEADERS), ("/ui/api", {})])
def test_lifecycle_no_violation(service, video, monkeypatch, prefix, headers):
    module, client, _ = service
    entered, release = threading.Event(), threading.Event()

    def stub(path):
        entered.set()
        assert release.wait(3)
        return []

    monkeypatch.setattr(module, "analyze_video", stub)
    try:
        response = upload(client, video, prefix, headers)
        assert response.status_code == 200
        assert set(response.json()) == {"job_id"}
        job_id = response.json()["job_id"]
        assert entered.wait(2)
        assert client.get(prefix + "/jobs/" + job_id, headers=headers).json() == {"job_id": job_id, "status": "processing"}
    finally:
        release.set()
    assert wait_job(client, job_id, prefix, headers) == {
        "job_id": job_id, "status": "done", "verdict": "no_violation", "violations": []}


def test_violation_jpeg_schema(service, video, monkeypatch):
    module, client, _ = service
    monkeypatch.setattr(module, "analyze_video", lambda path: [{
        "type": "test event", "timecode_sec": 0.4, "description": "synthetic test", "rule": "test-only"}])
    job = wait_job(client, upload(client, video).json()["job_id"])
    assert set(job) == {"job_id", "status", "verdict", "violations"}
    assert job["verdict"] == "violation"
    v = job["violations"][0]
    assert set(v) == {"type", "timecode_sec", "description", "rule", "evidence_frames"}
    assert v["timecode_sec"] == 0.4
    assert 1 <= len(v["evidence_frames"]) <= 3
    for frame in v["evidence_frames"]:
        assert set(frame) == {"timestamp_sec", "image_base64"}
        raw = base64.b64decode(frame["image_base64"], validate=True)
        assert raw.startswith(b"\xff\xd8") and raw.endswith(b"\xff\xd9")
        assert cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR).shape == (24, 32, 3)
    assert client.get("/ui/api/jobs/" + job["job_id"]).json()["violations"][0]["rule"] == "test-only"


def test_model_failure_and_cleanup(service, video, monkeypatch):
    module, client, _ = service

    def stub(path):
        raise RuntimeError("secret-payload-do-not-log")

    monkeypatch.setattr(module, "analyze_video", stub)
    job = wait_job(client, upload(client, video).json()["job_id"])
    assert job["status"] == "failed"
    assert job["error"] == "analysis failed (RuntimeError)"
    # Worker cleanup follows the terminal DB update.
    deadline = time.monotonic() + 2
    while list(module.UPLOAD_DIR.iterdir()) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not list(module.UPLOAD_DIR.iterdir())


def test_corrupt_video(service):
    _, client, _ = service
    response = client.post("/api/v1/analyze", headers=HEADERS, files={"file": ("bad.mov", b"not video")})
    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "failed"
    assert "no decodable frames" in job["error"]


def test_contract_snapshot(service):
    module, _, _ = service
    schema = module.app.openapi()
    contract = {"paths": {path: value for path, value in schema["paths"].items() if path.startswith("/api/v1/")},
                "schemas": schema["components"]["schemas"]}
    expected = json.loads((Path(__file__).parent / "api_contract.json").read_text())
    assert contract == expected

@pytest.mark.parametrize("timecode", [999.0, 1.0])
def test_evidence_fallback(service, video, monkeypatch, timecode):
    module, client, _ = service
    monkeypatch.setattr(module, "analyze_video", lambda path: [{
        "type": "test", "timecode_sec": timecode, "description": "test"}])
    job = wait_job(client, upload(client, video).json()["job_id"])
    assert job["status"] == "done"
    evidence = job["violations"][0]["evidence_frames"]
    assert 1 <= len(evidence) <= 3
    assert any(frame["timestamp_sec"] == pytest.approx(0.9) for frame in evidence)
    assert cv2.imdecode(np.frombuffer(base64.b64decode(evidence[0]["image_base64"]), np.uint8), 1) is not None


def test_rule_flag_keeps_ui_rule(service, video, monkeypatch):
    module, client, _ = service
    monkeypatch.setattr(module, "INCLUDE_RULE", False)
    monkeypatch.setattr(module, "analyze_video", lambda path: [{
        "type": "test", "timecode_sec": 0, "description": "test", "rule": "test rule"}])
    job = wait_job(client, upload(client, video).json()["job_id"])
    assert "rule" not in job["violations"][0]
    assert client.get("/ui/api/jobs/" + job["job_id"]).json()["violations"][0]["rule"] == "test rule"


def test_timeout_includes_queue_and_cannot_be_overwritten(service, video, monkeypatch):
    module, client, _ = service
    monkeypatch.setattr(module, "JOB_TIMEOUT_SEC", 0.15)
    entered, release = threading.Event(), threading.Event()

    def stub(path):
        entered.set()
        assert release.wait(3)
        return []

    monkeypatch.setattr(module, "analyze_video", stub)
    try:
        first = upload(client, video).json()["job_id"]
        assert entered.wait(1)
        second = upload(client, video).json()["job_id"]
        for job_id in (first, second):
            job = wait_job(client, job_id)
            assert job["status"] == "failed" and "timeout" in job["error"]
    finally:
        release.set()
    deadline = time.monotonic() + 2
    while list(module.UPLOAD_DIR.iterdir()) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not list(module.UPLOAD_DIR.iterdir())
    for job_id in (first, second):
        assert client.get("/api/v1/jobs/" + job_id, headers=HEADERS).json()["status"] == "failed"


def test_structured_log_has_no_payload(service, video, monkeypatch, caplog):
    module, client, _ = service
    monkeypatch.setattr(module, "analyze_video", lambda path: [])
    with caplog.at_level("INFO", logger=module.log.name):
        job = wait_job(client, upload(client, video).json()["job_id"])
    records = [json.loads(r.message) for r in caplog.records if r.message.startswith('{')]
    assert records
    assert set(records[-1]) == {"job_id", "duration_sec", "verdict"}
    assert records[-1]["job_id"] == job["job_id"]
    assert "unit-test-key" not in caplog.text


def test_fallback_when_seek_returns_false(service, video, monkeypatch):
    module, _, _ = service
    capture = module.cv2.VideoCapture

    class NoSeek:
        def __init__(self, path):
            self.cap = capture(path)

        def set(self, prop, value):
            return False

        def __getattr__(self, name):
            return getattr(self.cap, name)

    monkeypatch.setattr(module.cv2, "VideoCapture", NoSeek)
    evidence = module.frame_b64(video, 0.5)
    assert evidence["timestamp_sec"] == pytest.approx(0.5)


def test_persisted_result_and_interrupted_upload_on_restart(service, video):
    module, client, fake = service
    from fastapi.testclient import TestClient
    job = wait_job(client, upload(client, video).json()["job_id"])
    fake.create_job("interrupted")
    orphan = module.UPLOAD_DIR / "orphan.mov"
    orphan.write_bytes(b"interrupted")
    # Simulate another startup after all submitted work has completed.
    with TestClient(module.app) as restarted:
        assert restarted.get("/api/v1/jobs/" + job["job_id"], headers=HEADERS).json() == job
        assert restarted.get("/api/v1/jobs/interrupted", headers=HEADERS).json()["status"] == "failed"
        assert not orphan.exists()


@pytest.mark.parametrize('include_rule', [True, False])
@pytest.mark.parametrize('rule_in_description', [True, False])
@pytest.mark.parametrize('rule', ['Документ, пункт: проверенное правило', '', '   '])
def test_jury_rule_description_is_separate_from_ui(service, video, monkeypatch, include_rule, rule_in_description, rule):
    module, client, _ = service
    monkeypatch.setattr(module, 'INCLUDE_RULE', include_rule)
    monkeypatch.setattr(module, 'RULE_IN_DESCRIPTION', rule_in_description)
    monkeypatch.setattr(module, 'analyze_video', lambda path: [{
        'type': 'test', 'timecode_sec': 0, 'description': 'Описание', 'rule': rule}])
    job = wait_job(client, upload(client, video).json()['job_id'])
    violation = job['violations'][0]
    appended = not include_rule and rule_in_description and bool(rule.strip())
    assert violation['description'] == 'Описание' + (f' Правило: {rule}' if appended else '')
    assert ('rule' in violation) == include_rule
    ui = client.get('/ui/api/jobs/' + job['job_id']).json()['violations'][0]
    assert ui['description'] == 'Описание'
    assert ui['rule'] == rule
    assert client.get('/api/v1/jobs/' + job['job_id'], headers=HEADERS).json() == job


@pytest.mark.parametrize('enabled', [True, False])
def test_missing_rule_does_not_change_description(service, video, monkeypatch, enabled):
    module, client, _ = service
    monkeypatch.setattr(module, 'INCLUDE_RULE', False)
    monkeypatch.setattr(module, 'RULE_IN_DESCRIPTION', enabled)
    monkeypatch.setattr(module, 'analyze_video', lambda path: [{
        'type': 'test', 'timecode_sec': 0, 'description': 'Описание без правила'}])
    job = wait_job(client, upload(client, video).json()['job_id'])
    assert job['violations'][0]['description'] == 'Описание без правила'
    assert 'rule' not in job['violations'][0]
