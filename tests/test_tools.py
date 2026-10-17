import argparse
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from tools import common, eval_labels, load_test, test_client

ROOT = Path(__file__).resolve().parents[1]


def args():
    return argparse.Namespace(base_url="http://localhost:8000", api_key="never-print-this-key",
                              timeout=1, request_timeout=1, poll_interval=0.01)


@pytest.mark.parametrize("script", ["test_client.py", "load_test.py", "eval_labels.py"])
def test_help(script):
    response = subprocess.run([sys.executable, str(ROOT / "tools" / script), "--help"], capture_output=True, text=True, timeout=10)
    assert response.returncode == 0 and "usage:" in response.stdout


def test_http_error_is_clear_and_does_not_dump_body(video, monkeypatch):
    response = requests.Response()
    response.status_code = 401
    response._content = b"never-print-this-key BASE64-PAYLOAD"
    monkeypatch.setattr(requests.Session, "request", lambda *a, **kw: response)
    with pytest.raises(common.ToolError, match="HTTP 401") as error:
        common.analyze(args(), video)
    assert "never-print-this-key" not in str(error.value)
    assert "BASE64" not in str(error.value)


def test_poll_deadline(video, monkeypatch):
    response = requests.Response()
    response.status_code = 200
    responses = iter([{"job_id": "abc123"}])
    monkeypatch.setattr(response, "json", lambda: next(responses, {"status": "processing"}))
    monkeypatch.setattr(requests.Session, "request", lambda *a, **kw: response)
    config = args()
    config.timeout = 0.03
    with pytest.raises(common.ToolError, match="deadline"):
        common.analyze(config, video)


def test_failed_job_is_nonzero(monkeypatch, capsys):
    def fail(*a, **kw):
        raise common.ToolError("job failed")
    monkeypatch.setattr(test_client, "analyze", fail)
    monkeypatch.setattr(load_test, "analyze", fail)
    assert test_client.main(["http://localhost:8000", "never-print-this-key", "tiny.mov"]) == 1
    assert load_test.main(["http://localhost:8000", "never-print-this-key", "tiny.mov"]) == 1
    assert "never-print-this-key" not in capsys.readouterr().err


def test_labels_timestamp_parsing():
    assert eval_labels.parse_ts("1минута 8 секунда") == 68
    assert eval_labels.parse_ts("22 секунда") == 22
    assert eval_labels.parse_ts(7) == 7
    assert eval_labels.parse_ts(None) is None
    with pytest.raises(ValueError):
        eval_labels.parse_ts("unknown")


def test_missing_dataset_is_nonzero(tmp_path):
    assert eval_labels.main(["http://localhost:8000", "test", str(tmp_path)]) == 1
