"""Model/rules hooks remain offline, compatible, and optional."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from test_api import upload, wait_job


def test_legacy_model_signature(service, video, monkeypatch):
    module, client, _ = service
    calls = []
    def model(path):
        calls.append(path)
        return []
    monkeypatch.setattr(module, 'analyze_video', model)
    assert wait_job(client, upload(client, video).json()['job_id'])['status'] == 'done'
    assert len(calls) == 1


def test_model_receives_monotonic_deadline(service, video, monkeypatch):
    module, client, _ = service
    calls = []
    def model(path, *, deadline):
        calls.append(deadline)
        return []
    monkeypatch.setattr(module, 'analyze_video', model)
    before = time.monotonic()
    assert wait_job(client, upload(client, video).json()['job_id'])['status'] == 'done'
    after = time.monotonic()
    margin = min(10, module.JOB_TIMEOUT_SEC * .1)
    assert before + module.JOB_TIMEOUT_SEC - margin <= calls[0] <= after + module.JOB_TIMEOUT_SEC - margin


@pytest.mark.parametrize('model_rule', ['', 'model-supplied'])
def test_local_rule_only_fills_missing_rule(service, video, monkeypatch, model_rule):
    module, client, _ = service
    monkeypatch.setattr(module, 'analyze_video', lambda path: [{
        'type': 'test', 'timecode_sec': 0, 'description': 'description', 'rule': model_rule}])
    calls = []
    def lookup(kind):
        calls.append(kind)
        return {'rule': 'local rule'}
    monkeypatch.setattr(module, 'lookup_rule', lookup)
    job = wait_job(client, upload(client, video).json()['job_id'], '/ui/api', {})
    assert job['status'] == 'done'
    assert job['violations'][0]['rule'] == (model_rule or 'local rule')
    assert calls == ([] if model_rule else ['test'])


def test_rule_lookup_failure_does_not_fail_job_or_log_payload(service, video, monkeypatch, caplog):
    module, client, _ = service
    monkeypatch.setattr(module, 'analyze_video', lambda path: [{
        'type': 'test', 'timecode_sec': 0, 'description': 'description'}])
    def lookup(kind):
        raise RuntimeError('private-key-and-base64-payload')
    monkeypatch.setattr(module, 'lookup_rule', lookup)
    job = wait_job(client, upload(client, video).json()['job_id'], '/ui/api', {})
    assert job['status'] == 'done' and job['violations'][0]['rule'] == ''
    assert 'rules_lookup_failed' in caplog.text
    assert 'private-key-and-base64-payload' not in caplog.text


def test_default_demo_is_off(service, video):
    module, client, _ = service
    assert module.DEMO_MODE is False
    assert module.original_stub(str(video)) == []
    assert client.get('/health').json()['demo_mode'] is False
    assert 'DEMO_MODE' not in (Path(__file__).resolve().parents[1] / '.env.example').read_text()


def test_explicit_demo_stub_is_synthetic_with_evidence(service, video, monkeypatch):
    module, client, _ = service
    monkeypatch.setattr(module, 'DEMO_REQUESTED', True)
    monkeypatch.setattr(module, 'DEMO_MODE', True)
    monkeypatch.setattr(module, 'analyze_video', module.original_stub)
    job = wait_job(client, upload(client, video).json()['job_id'], '/ui/api', {})
    violation = job['violations'][0]
    assert violation['type'] == 'ДЕМО'
    assert violation['description'] == 'Демонстрационный результат, не настоящий анализ'
    assert violation['rule'] == '—'
    assert 0 <= violation['timecode_sec'] < 1
    assert violation['evidence_frames']
    assert client.get('/health').json()['demo_mode'] is True


def test_demo_cannot_override_real_model():
    code = '''
import importlib.machinery, json, sys, types
model = types.ModuleType('model_service')
model.__spec__ = importlib.machinery.ModuleSpec('model_service', loader=None)
model.analyze_video = lambda path: []
sys.modules['model_service'] = model
import main
print(json.dumps(main.health()))
'''
    env = {**os.environ, 'DEMO_MODE': 'true'}
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    health = json.loads(result.stdout)
    assert health['model_loaded'] is True
    assert health['demo_mode'] is False
