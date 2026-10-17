"""Diagnostics use fake model modules, never a training model or real secrets."""
from pathlib import Path
import socket
import time

import pytest

from tools import check_model,bench_model,model_support


@pytest.fixture
def model(monkeypatch):
    def configure(function):
        monkeypatch.setattr(check_model,'load_model',lambda:(function,[]))
        monkeypatch.setattr(bench_model,'load_model',lambda:(function,[]))
    return configure


def test_good_model_and_both_signatures(model,video,capsys):
    called=[]
    def function(path,deadline=None):
        called.append(deadline)
        print('base64-do-not-show')
        return [{'type':'test','timecode_sec':.2,'description':'synthetic','rule':''}]
    model(function)
    assert check_model.main(['--video',str(video)])==0
    assert called[0] is not None
    assert 'base64-do-not-show' not in capsys.readouterr().out
    model(lambda path:[])
    assert check_model.main(['--video',str(video)])==0


@pytest.mark.parametrize('result',[None,{},[{}],[{'type':'','timecode_sec':0,'description':'x'}],
    [{'type':'x','timecode_sec':float('nan'),'description':'x'}],
    [{'type':'x','timecode_sec':9,'description':'x'}],
    [{'type':'x','timecode_sec':0,'description':'x','rule':object()}]])
def test_malformed_model_fails(model,video,result):
    model(lambda path:result)
    assert check_model.main(['--video',str(video)])==1
    assert bench_model.main(['--videos',str(video),'--count','1','--workers','1'])==1


def test_slow_model_and_queue_budget(model,video,monkeypatch,capsys):
    monkeypatch.setenv('JOB_TIMEOUT_SEC','0.02')
    def slow(path,deadline=None):
        time.sleep(.04)
        return []
    model(slow)
    assert check_model.main(['--video',str(video)])==1
    assert bench_model.main(['--videos',str(video),'--count','2','--workers','1'])==1
    assert 'TOO SLOW' in capsys.readouterr().out


def test_bench_sweep_reports_measured_safe_workers(model,video,capsys):
    model(lambda path:[])
    assert bench_model.main(['--videos',str(video),'--count','3','--workers','2','--sweep'])==0
    assert 'Largest safe MEASURED WORKERS among 1..4: 4' in capsys.readouterr().out


@pytest.mark.parametrize('source', ['import openai','from google import genai','from huggingface_hub import InferenceClient',
    'import boto3','import importlib\nimportlib.import_module("anthropic")'])
def test_cloud_imports_rejected_before_execution(tmp_path,source):
    (tmp_path/'model_service.py').write_text(source,encoding='utf-8')
    errors,_=model_support.scan_sources(tmp_path)
    assert errors
    with pytest.raises(model_support.ModelCheckError): model_support.load_model(tmp_path)


def test_recursive_local_scan_and_url_warning_only(tmp_path):
    (tmp_path/'model_service.py').write_text('import helper\ndef analyze_video(path): return []',encoding='utf-8')
    (tmp_path/'helper.py').write_text('LINK="https://example.invalid/sensitive-hidden"',encoding='utf-8')
    errors,warnings=model_support.scan_sources(tmp_path)
    assert not errors and warnings and 'sensitive-hidden' not in str(warnings)
    (tmp_path/'helper.py').write_text('import groq',encoding='utf-8')
    assert model_support.scan_sources(tmp_path)[0]


def test_offline_guard_blocks_network_and_restores_environment(monkeypatch):
    monkeypatch.delenv('HF_HUB_OFFLINE',raising=False)
    original=socket.getaddrinfo
    with model_support.offline_guard():
        with pytest.raises(model_support.ModelCheckError): socket.getaddrinfo('external.invalid',443)
        with socket.socket() as sock:
            with pytest.raises(model_support.ModelCheckError): sock.connect(('192.0.2.1',443))
        assert socket.getaddrinfo('127.0.0.1',80)
    assert socket.getaddrinfo is original


def test_missing_model_message(tmp_path):
    with pytest.raises(model_support.ModelCheckError,match='missing'): model_support.load_model(tmp_path)
