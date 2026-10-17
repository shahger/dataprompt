import io
import json
from pathlib import Path
import zipfile

import pytest
from tools import handover


def archive_blob(entries):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        for name,content in entries.items(): archive.writestr(name,content)
    return stream.getvalue()


@pytest.mark.parametrize('name',['.env','nested/.env.local','node_modules/a.js','.downloads/a','a.MOV','x/__pycache__/a.pyc','.venv/a'])
def test_archive_rejects_private_or_cached_files(name):
    bad,secret,_=handover.inspect_archive(archive_blob({name:'safe'}),'test-secret-not-in-archive')
    assert bad==1 and secret==0


def test_archive_permits_examples_and_rejects_secret_content():
    key='fake-unit-secret-with-at-least-32-characters'
    assert handover.inspect_archive(archive_blob({'.env.example':'API_KEY=example','README.md':'safe'}),key)[:2]==(0,0)
    assert handover.inspect_archive(archive_blob({'README.md':key}),key)[:2]==(0,1)


def test_finalize_requires_real_model_and_preserves_other_text(tmp_path):
    path=tmp_path/'jury.md'
    text='before\n'+handover.START+'\npre-model warning\n'+handover.END+'\nafter\n'
    path.write_text(text,encoding='utf-8')
    with pytest.raises(ValueError): handover.finalize_doc(path,{'model_loaded':False,'demo_mode':False})
    assert path.read_text()==text
    assert handover.finalize_doc(path,{'model_loaded':True,'demo_mode':False})
    assert path.read_text()=='before\n\nafter\n'
    assert not handover.finalize_doc(path,{'model_loaded':True,'demo_mode':False})


def test_allow_stub_does_not_hide_unfinalized_note(monkeypatch,tmp_path,capsys):
    (tmp_path/'docs').mkdir()
    (tmp_path/'docs/JURY_INSTRUCTIONS.md').write_text(handover.START+'\nwarning\n'+handover.END)
    (tmp_path/'.env').write_text('API_KEY=fake-unit-secret-with-at-least-32-characters\nINCLUDE_RULE=false')
    (tmp_path/'.env.example').write_text('API_KEY=change-me')
    monkeypatch.setattr(handover,'containers_healthy',lambda root:True)
    monkeypatch.setattr(handover,'http_health',lambda url:{'status':'ok','model_loaded':False,'demo_mode':False})
    monkeypatch.setattr(handover,'secret_matches',lambda root,key:0)
    monkeypatch.setattr(handover,'external_resources',lambda root:0)
    monkeypatch.setattr(handover,'dirty',lambda root:False)
    class Response: status_code=401
    monkeypatch.setattr(handover.requests,'get',lambda *a,**k:Response())
    assert handover.preflight(True,tmp_path)==1
    output=capsys.readouterr().out
    assert 'WARN | real model' in output and 'FAIL | pre-model note' in output
    assert 'fake-unit-secret-with-at-least-32-characters' not in output


def test_safe_logs_only_permit_known_metadata():
    record={'job_id':'a'*32,'duration_sec':1.2,'verdict':'violation'}
    unsafe={**record,'image_base64':'NEVER_SHOW'}
    text='INFO: '+json.dumps(record)+'\nINFO: '+json.dumps(unsafe)+'\nAPI_KEY=NEVER_SHOW'
    output=handover.safe_job_logs(text)
    assert len(output)==1 and 'NEVER_SHOW' not in ''.join(output)
