"""Mode A checks against the local stack. No secrets or payloads are printed."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import cv2
import numpy as np
import requests

try:
    from .check_public import read_api_key
except ImportError:
    from check_public import read_api_key

ROOT = Path(__file__).resolve().parents[1]


def require(condition, label):
    if not condition:
        raise RuntimeError(label)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args(argv)
    base = args.base_url.rstrip('/')
    report = {}
    try:
        before = hashlib.sha256((ROOT / '.env').read_bytes()).digest()
        key = read_api_key()
        headers = {'X-API-Key': key}
        for path in (ROOT / 'static').rglob('*'):
            if path.suffix in {'.html', '.js', '.css'}:
                require(key.encode() not in path.read_bytes(), 'secret excluded from static assets')
        report['secret_not_in_static'] = True
        def ready():
            until = time.monotonic() + 120
            while time.monotonic() < until:
                try:
                    response = requests.get(base + '/health', timeout=3)
                    if response.ok and response.json().get('status') == 'ok':
                        return response.json()
                except (requests.RequestException, ValueError):
                    pass
                time.sleep(.5)
            raise RuntimeError('health deadline')
        health = ready()
        require(health.get('model_loaded') is False and health.get('demo_mode') is False, 'expected default stub, no demo')
        report['health'] = health
        home = requests.get(base + '/', timeout=10)
        require(home.ok and 'lang="ru"' in home.text and 'Контроль кассовой дисциплины' in home.text, 'Russian index')
        require(requests.get(base + '/review/test/session', timeout=10).text == home.text, 'SPA deep link')
        for path in ['/api/missing', '/ui/api/missing', '/health/missing', '/assets/missing.js']:
            require(requests.get(base + path, timeout=10).status_code == 404, 'reserved route 404')
        assets = list((ROOT / 'static/assets').iterdir())
        for path in assets:
            response = requests.get(base + '/assets/' + path.name, timeout=10)
            require(response.status_code == 200 and len(response.content) == path.stat().st_size, 'asset delivery')
        report['assets_served'] = len(assets)
        require(requests.get(base + '/api/v1/jobs/unknown', timeout=10).status_code == 401, 'missing key')
        require(requests.get(base + '/api/v1/jobs/unknown', headers={'X-API-Key': 'deliberately-wrong'}, timeout=10).status_code == 401, 'wrong key')
        require(requests.get(base + '/api/v1/jobs/unknown', headers=headers, timeout=10).status_code == 404, 'unknown job')
        work = ROOT / '.test-artifacts/stack-check'
        work.mkdir(parents=True, exist_ok=True)
        videos = []
        for n in range(3):
            path = work / f'test-{n}.mov'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (64, 48))
            require(writer.isOpened(), 'synthetic MOV writer')
            try:
                for frame in range(20):
                    writer.write(np.full((48, 64, 3), (frame + n) * 8, dtype=np.uint8))
            finally:
                writer.release()
            videos.append(path)
        def one(path, prefix='/api/v1', auth=None):
            start = time.monotonic()
            with path.open('rb') as stream:
                response = requests.post(base + prefix + '/analyze', headers=auth, files={'file': (path.name, stream, 'video/quicktime')}, timeout=30)
            require(response.status_code == 200, 'upload status')
            submitted = response.json()
            require(set(submitted) == {'job_id'} and isinstance(submitted['job_id'], str), 'submit schema')
            job_id = submitted['job_id']
            while time.monotonic() - start < 300:
                response = requests.get(base + prefix + '/jobs/' + job_id, headers=auth, timeout=10)
                require(response.status_code == 200, 'poll status')
                result = response.json()
                if result.get('status') != 'processing':
                    break
                require(set(result) == {'job_id', 'status'}, 'processing schema')
                time.sleep(.05)
            else:
                raise RuntimeError('job deadline')
            require(result == {'job_id': job_id, 'status': 'done', 'verdict': 'no_violation', 'violations': []}, 'done schema')
            return result, time.monotonic() - start
        result, duration = one(videos[0], auth=headers)
        report['single_seconds'] = round(duration, 3)
        report['persisted_job_id'] = result['job_id']
        with ThreadPoolExecutor(max_workers=3) as pool:
            durations = list(pool.map(lambda path: one(path, auth=headers)[1], videos))
        report['three_concurrent_seconds'] = [round(value, 3) for value in durations]
        report['ui_route_seconds'] = round(one(videos[0], '/ui/api', {})[1], 3)
        if args.restart:
            restarted = subprocess.run(['docker', 'compose', 'restart', 'api'], cwd=ROOT, capture_output=True, timeout=60)
            require(restarted.returncode == 0, 'api restart command')
            ready()
            response = requests.get(base + '/api/v1/jobs/' + result['job_id'], headers=headers, timeout=10)
            require(response.status_code == 200 and response.json() == result, 'persistence after restart')
            report['restart_persistence'] = True
        require(hashlib.sha256((ROOT / '.env').read_bytes()).digest() == before, 'env preserved')
        report['env_unchanged'] = True
        (work / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True))
        return 0
    except Exception as error:
        # Do not print exception text, HTTP bodies, headers, or credentials.
        print(f'Stack verification failed ({type(error).__name__}); inspect local service state.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
