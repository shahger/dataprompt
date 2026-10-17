"""Offline diagnostics for local notebook exports; no video/result payload output."""
import ast
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import importlib.util
import ipaddress
import json
import logging
import math
import os
from pathlib import Path
import socket
import sys

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from model_contract import invoke_model

FORBIDDEN = ('openai','anthropic','google.generativeai','google.genai','vertexai','cohere',
             'mistralai','groq','replicate','boto3','botocore','litellm','azure.ai.inference','azure.ai.openai')
INFERENCE = {'InferenceClient','AsyncInferenceClient','InferenceApi'}


class ModelCheckError(Exception):
    pass


class OfflineBlocked(ModelCheckError):
    pass


def execute_model(function,path,submitted,timeout):
    try:
        return invoke_model(function,path,submitted,timeout)
    except OfflineBlocked:
        raise ModelCheckError('offline guard blocked a model network call') from None
    except Exception:
        raise ModelCheckError('model execution failed; exception details suppressed') from None


def forbidden(name):
    return any(name == prefix or name.startswith(prefix+'.') for prefix in FORBIDDEN) or name.startswith('huggingface_hub.inference') or any(name == 'huggingface_hub.'+item for item in INFERENCE)


def scan_sources(root=ROOT):
    root=Path(root).resolve()
    pending=[root/'model_service.py']; visited=set(); errors=[]; warnings=[]
    def add_module(parts,base=root):
        segments=parts.strip('.').split('.')
        for index in range(1,len(segments)+1):
            target=base.joinpath(*segments[:index])
            candidates=[target/'__init__.py']
            if index==len(segments): candidates.append(target.with_suffix('.py'))
            for path in candidates:
                if path.is_file() and path.resolve().is_relative_to(root): pending.append(path.resolve())
    while pending:
        path=pending.pop()
        if path in visited or not path.is_file(): continue
        visited.add(path)
        try: tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        except (OSError,SyntaxError,UnicodeError):
            errors.append(f'{path.relative_to(root)}: source cannot be parsed'); continue
        aliases={}
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.Import):
                names=[alias.name for alias in node.names]
                for alias in node.names: aliases[alias.asname or alias.name.split('.')[0]]=alias.name if alias.asname else alias.name.split('.')[0]
            elif isinstance(node,ast.ImportFrom):
                module=node.module or ''
                names=[module]+[module+'.'+alias.name for alias in node.names]
                for alias in node.names: aliases[alias.asname or alias.name]=module+'.'+alias.name
                base=path.parent
                for _ in range(max(0,node.level-1)): base=base.parent
                if node.level:
                    for name in names:
                        if name: add_module(name,base)
            for name in names:
                if forbidden(name): errors.append(f'{path.relative_to(root)}:{node.lineno}: forbidden cloud AI import')
                if name: add_module(name)
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and ('http://' in node.value or 'https://' in node.value):
                warnings.append(f'{path.relative_to(root)}:{node.lineno}: hard-coded URL (value hidden)')
        def qualified(node):
            if isinstance(node,ast.Name): return aliases.get(node.id,node.id)
            if isinstance(node,ast.Attribute): return qualified(node.value)+'.'+node.attr
            return ''
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call): continue
            name=qualified(node.func)
            if forbidden(name): errors.append(f'{path.relative_to(root)}:{node.lineno}: forbidden cloud AI call')
            if name in {'importlib.import_module','__import__'} and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                module=node.args[0].value
                if forbidden(module): errors.append(f'{path.relative_to(root)}:{node.lineno}: forbidden dynamic cloud AI import')
                add_module(module)
    return sorted(set(errors)),sorted(set(warnings))


def loopback(host):
    if isinstance(host,bytes): host=host.decode('ascii',errors='ignore')
    if str(host).lower().rstrip('.') == 'localhost': return True
    try:
        address=ipaddress.ip_address(str(host).split('%')[0])
        return address.is_loopback or bool(getattr(address,'ipv4_mapped',None) and address.ipv4_mapped.is_loopback)
    except ValueError: return False


@contextmanager
def offline_guard(enabled=True):
    if not enabled:
        yield; return
    previous={name:os.environ.get(name) for name in ['HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','NO_PROXY']}
    original_connect,original_connect_ex,original_dns=socket.socket.connect,socket.socket.connect_ex,socket.getaddrinfo
    def connect(sock,address):
        if sock.family == getattr(socket,'AF_UNIX',object()): return original_connect(sock,address)
        if not isinstance(address,tuple) or not loopback(address[0]): raise OfflineBlocked('offline guard blocked non-loopback connection')
        return original_connect(sock,address)
    def connect_ex(sock,address):
        if not isinstance(address,tuple) or not loopback(address[0]): raise OfflineBlocked('offline guard blocked non-loopback connection')
        return original_connect_ex(sock,address)
    def dns(host,*args,**kwargs):
        if host is not None and not loopback(host): raise OfflineBlocked('offline guard blocked non-loopback DNS')
        return original_dns(host,*args,**kwargs)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',NO_PROXY='*')
    socket.socket.connect=connect; socket.socket.connect_ex=connect_ex; socket.getaddrinfo=dns
    try: yield
    finally:
        socket.socket.connect=original_connect; socket.socket.connect_ex=original_connect_ex; socket.getaddrinfo=original_dns
        for name,value in previous.items():
            if value is None: os.environ.pop(name,None)
            else: os.environ[name]=value


@contextmanager
def quiet_model():
    level=logging.root.manager.disable
    with open(os.devnull,'w') as sink,redirect_stdout(sink),redirect_stderr(sink):
        logging.disable(logging.CRITICAL)
        try: yield
        finally: logging.disable(level)


def load_model(root=ROOT):
    root=Path(root)
    path=root/'model_service.py'
    if not path.is_file(): raise ModelCheckError('model_service.py is missing / модель ещё не подключена')
    errors,warnings=scan_sources(root)
    if errors: raise ModelCheckError('forbidden/invalid model source: '+str(len(errors))+' issue(s)\n'+'\n'.join(errors))
    spec=importlib.util.spec_from_file_location('model_service',path)
    module=importlib.util.module_from_spec(spec)
    sys.modules['model_service']=module
    try:
        with quiet_model():
            spec.loader.exec_module(module)
            function=getattr(module,'analyze_video',None)
    except OfflineBlocked:
        raise ModelCheckError('offline guard blocked a model import network call') from None
    except Exception:
        raise ModelCheckError('model import failed; exception details suppressed') from None
    if not callable(function): raise ModelCheckError('analyze_video is missing or not callable')
    return function,warnings


def video_duration(path):
    if not Path(path).is_file(): raise ModelCheckError('video must be an existing local file')
    cap=cv2.VideoCapture(str(path))
    try:
        fps,count=cap.get(cv2.CAP_PROP_FPS),cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not cap.isOpened() or not cap.read()[0] or not math.isfinite(fps) or fps<=0 or not math.isfinite(count) or count<=0:
            raise ModelCheckError('video is unreadable or duration is unavailable')
        return count/fps
    finally: cap.release()


def validate_result(result,duration):
    if not isinstance(result,list): raise ModelCheckError('result must be a list')
    try: json.dumps(result,allow_nan=False)
    except (ValueError,TypeError,OverflowError): raise ModelCheckError('result is not finite JSON data') from None
    for index,item in enumerate(result):
        if not isinstance(item,dict): raise ModelCheckError(f'item {index}: expected dict')
        if set(item)-{'type','timecode_sec','description','rule'}: raise ModelCheckError(f'item {index}: unexpected fields')
        for key in ['type','description']:
            if not isinstance(item.get(key),str) or not item[key].strip(): raise ModelCheckError(f'item {index}: {key} must be a nonempty string')
        value=item.get('timecode_sec')
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=duration+1:
            raise ModelCheckError(f'item {index}: invalid/out-of-range timecode_sec')
        if 'rule' in item and not isinstance(item['rule'],str): raise ModelCheckError(f'item {index}: rule must be a string')
    return len(result)


def timeout_seconds():
    try: value=float(os.environ.get('JOB_TIMEOUT_SEC','270'))
    except ValueError: raise ModelCheckError('JOB_TIMEOUT_SEC must be positive') from None
    if not math.isfinite(value) or value<=0: raise ModelCheckError('JOB_TIMEOUT_SEC must be positive')
    return value
