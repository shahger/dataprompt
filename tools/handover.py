"""Secret-safe handover checks/archive helpers for PowerShell 5.1 wrappers."""
import argparse
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

import requests

ROOT=Path(__file__).resolve().parents[1]
PUBLIC='https://reverence-culpable-cupping.ngrok-free.dev'
NAMESPACES=('http://www.w3.org/2000/svg','http://www.w3.org/1998/Math/MathML',
            'http://www.w3.org/1999/xlink','http://www.w3.org/XML/1998/namespace','http://www.w3.org/1999/xhtml')
START='<!-- PRE-MODEL-NOTE:START -->'; END='<!-- PRE-MODEL-NOTE:END -->'


def config(root=ROOT):
    result={}
    for line in (Path(root)/'.env').read_text(encoding='utf-8-sig').splitlines():
        name,separator,value=line.strip().partition('=')
        if not separator or name not in {'API_KEY','INCLUDE_RULE'}: continue
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in {'"',"'"}: value=value[1:-1]
        else: value=value.split(' #',1)[0].rstrip()
        result[name]=value
    return result


def run(command,root=ROOT):
    return subprocess.run(command,cwd=root,capture_output=True,timeout=60)


def tracked_files(root=ROOT):
    result=run(['git','ls-files','-z'],root)
    if result.returncode: raise RuntimeError('git unavailable')
    return [name.decode('utf-8') for name in result.stdout.split(b'\0') if name]


def secret_matches(root,key):
    if not key: raise ValueError('missing key')
    matches=0
    for name in tracked_files(root):
        path=(Path(root)/name).resolve()
        if not path.is_relative_to(Path(root).resolve()): raise ValueError('tracked path outside project')
        if path.is_file() and key.encode('utf-8') in path.read_bytes(): matches+=1
    return matches


def external_resources(root=ROOT):
    count=0
    for path in (Path(root)/'static').rglob('*'):
        if path.suffix not in {'.html','.js','.css'}: continue
        text=path.read_text(encoding='utf-8-sig')
        for namespace in NAMESPACES: text=text.replace(namespace,'')
        count+=len(re.findall(r'https?://',text,re.I))
        count+=len(re.findall(r'''(?:src|href)\s*=\s*["']\s*//|url\(\s*["']?\s*//''',text,re.I))
    return count


def http_health(base):
    response=requests.get(base.rstrip('/')+'/health',headers={'ngrok-skip-browser-warning':'1'},timeout=10)
    response.raise_for_status()
    value=response.json()
    if not isinstance(value,dict) or value.get('status')!='ok': raise ValueError('bad health')
    return value


def model_ready(health):
    return health.get('model_loaded') is True and health.get('demo_mode') is False


def finalize_doc(path,health):
    if not model_ready(health): raise ValueError('real model required; demo must be off')
    path=Path(path); raw=path.read_bytes(); text=raw.decode('utf-8-sig')
    if START not in text and END not in text: return False
    if text.count(START)!=1 or text.count(END)!=1 or text.index(START)>text.index(END): raise ValueError('invalid note markers')
    begin=text.index(START); finish=text.index(END)+len(END)
    path.write_bytes((b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+(text[:begin]+text[finish:]).encode('utf-8'))
    return True


def containers_healthy(root=ROOT):
    result=run(['docker','compose','ps','--format','json'],root)
    if result.returncode: return False
    text=result.stdout.decode('utf-8').strip()
    rows=json.loads(text) if text.startswith('[') else [json.loads(line) for line in text.splitlines() if line]
    return all(any(row.get('Service')==name and row.get('State')=='running' and row.get('Health')=='healthy' for row in rows) for name in ['api','db'])


def dirty(root=ROOT):
    result=run(['git','status','--porcelain'],root)
    if result.returncode: raise RuntimeError('git unavailable')
    return bool(result.stdout.strip())


def preflight(allow_stub=False,root=ROOT,public=PUBLIC):
    failed=False
    def show(label,status,detail=''):
        nonlocal failed
        failed |= status=='FAIL'
        print(f'{status} | {label}'+(' | '+detail if detail else ''))
    try: show('containers healthy','PASS' if containers_healthy(root) else 'FAIL')
    except Exception: show('containers healthy','FAIL')
    try:
        health=http_health('http://localhost:8000')
        show('real model loaded; demo off','PASS' if model_ready(health) else 'WARN' if allow_stub else 'FAIL')
    except Exception: show('local health','FAIL')
    try:
        values=config(root); key=values.get('API_KEY','')
        example=(Path(root)/'.env.example').read_text(encoding='utf-8-sig')
        examples=[line.split('=',1)[1].strip() for line in example.splitlines() if line.startswith('API_KEY=')]
        show('API_KEY configured (value hidden)','PASS' if len(key)>=32 and key not in examples and not key.startswith('change-me') else 'FAIL')
        show('INCLUDE_RULE present and false','PASS' if values.get('INCLUDE_RULE','').lower()=='false' else 'FAIL')
        matches=secret_matches(root,key)
        show('secret scan of tracked files','PASS' if matches==0 else 'FAIL',f'matches={matches}')
    except Exception: show('local configuration / secret scan','FAIL')
    try:
        http_health(public)
        response=requests.get(public.rstrip('/')+'/api/v1/jobs/unknown',headers={'ngrok-skip-browser-warning':'1'},timeout=10)
        show('public health and unauthenticated API=401','PASS' if response.status_code==401 else 'FAIL')
    except Exception: show('public health and unauthenticated API=401','FAIL')
    try:
        count=external_resources(root)
        show('static resources local','PASS' if count==0 else 'FAIL',f'external_references={count}')
    except Exception: show('static resources local','FAIL')
    try: show('git working tree clean','FAIL' if dirty(root) else 'PASS')
    except Exception: show('git working tree clean','FAIL')
    try:
        text=(Path(root)/'docs/JURY_INSTRUCTIONS.md').read_text(encoding='utf-8-sig')
        show('pre-model note finalized','FAIL' if START in text or END in text else 'PASS')
    except Exception: show('pre-model note finalized','FAIL')
    return int(failed)


FORBIDDEN_PARTS={'.env','node_modules','.downloads','.npm-cache','.venv','__pycache__','.git','.public-session.json'}

def inspect_archive(blob,key):
    bad=secret=0; top=set()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for info in archive.infolist():
            parts=Path(info.filename.replace('\\','/')).parts
            top.add(parts[0])
            if any(part.lower() in FORBIDDEN_PARTS or (part.lower().startswith('.env') and part.lower()!='.env.example') for part in parts) or info.filename.lower().endswith('.mov'):
                bad+=1
            if not info.is_dir() and key.encode('utf-8') in archive.read(info): secret+=1
    return bad,secret,sorted(top)


def make_archive(out,root=ROOT):
    if dirty(root): print('WARN | working tree dirty; archive contains committed HEAD only')
    key=config(root).get('API_KEY','')
    if not key: raise ValueError('key unavailable for internal scan')
    result=run(['git','archive','--format=zip','HEAD'],root)
    if result.returncode: raise RuntimeError('git archive failed')
    bad,secret,top=inspect_archive(result.stdout,key)
    print(f'Archive scan: forbidden_entries={bad}; secret_matches={secret}')
    if bad or secret: return 1
    out=Path(out); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(result.stdout)
    print(f'PASS | archive bytes={len(result.stdout)}')
    print('Top-level entries: '+', '.join(top))
    return 0


def safe_job_logs(text):
    output=[]
    for line in text.splitlines()[-20:]:
        start=line.find('{')
        if start<0: continue
        try: record=json.loads(line[start:])
        except ValueError: continue
        if set(record)!={'job_id','duration_sec','verdict'}: continue
        if not isinstance(record['job_id'],str) or not re.fullmatch(r'[0-9a-f]{8,32}',record['job_id']): continue
        duration=record['duration_sec']
        if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<0: continue
        if record['verdict'] not in {'violation','no_violation','failed'}: continue
        output.append(json.dumps(record))
    return output


def status(root=ROOT,public=PUBLIC):
    result=run(['docker','compose','ps','--format','{{.Service}} {{.State}} {{.Health}}'],root)
    print('Docker:')
    if result.returncode: print('unavailable')
    else:
        for line in result.stdout.decode('utf-8',errors='replace').splitlines():
            if re.fullmatch(r'(api|db) [a-z]+ ?[a-z]*',line): print(line)
    for label,base in [('Local','http://localhost:8000'),('Public',public)]:
        try:
            health=http_health(base)
            print(f"{label}: ok; model_loaded={health.get('model_loaded') is True}; demo_mode={health.get('demo_mode') is True}; workers={int(health.get('workers',0))}")
        except Exception: print(label+': unavailable')
    # PowerShell handles process identity; this module never reads ngrok diagnostics/config.
    logs=run(['docker','compose','logs','--no-color','--tail','20','api'],root)
    print('Last 20 API lines, payload-safe job records only:')
    for line in safe_job_logs((logs.stdout+logs.stderr).decode('utf-8',errors='replace')): print(line)
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','finalize','archive','status'])
    parser.add_argument('--allow-stub',action='store_true')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.action=='preflight': return preflight(args.allow_stub)
        if args.action=='finalize':
            changed=finalize_doc(ROOT/'docs/JURY_INSTRUCTIONS.md',http_health('http://localhost:8000'))
            print('PASS | jury document finalized' if changed else 'PASS | jury document already finalized')
            return 0
        if args.action=='archive':
            if not args.out: parser.error('--out required')
            return make_archive(args.out)
        return status()
    except Exception:
        print('FAIL | operation could not be verified; no secret values displayed')
        return 1


if __name__=='__main__': raise SystemExit(main())
