"""Public smoke check. Credentials never become command-line arguments or output."""
import argparse
import os
from pathlib import Path
import sys

import requests

try:
    from . import test_client
except ImportError:
    import test_client

ROOT = Path(__file__).resolve().parents[1]


def read_api_key():
    # Read only API_KEY and never include values in exceptions or logs.
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if line.strip().startswith('API_KEY='):
            value = line.strip().split('=', 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            if value:
                return value
    raise ValueError('API_KEY missing')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Проверка публичного сервиса без вывода ключа')
    parser.add_argument('--base-url', default='https://reverence-culpable-cupping.ngrok-free.dev')
    parser.add_argument('--video', type=Path)
    args = parser.parse_args(argv)
    base = args.base_url.rstrip('/')
    warning_header = {'ngrok-skip-browser-warning': '1'}
    try:
        response = requests.get(base + '/health', headers=warning_header, timeout=30)
        response.raise_for_status()
        health = response.json()
        if health.get('status') != 'ok':
            raise ValueError('unhealthy')
        response = requests.get(base + '/api/v1/jobs/unknown', headers=warning_header, timeout=30)
        if response.status_code != 401:
            raise ValueError('auth check failed')
        print('Состояние сервиса: готов. Запрос без ключа: 401.')
        if args.video:
            # Call the existing smoke tool in-process: no secret process arguments.
            key = read_api_key()
            previous = os.environ.get('CASHIER_SKIP_BROWSER_WARNING')
            os.environ['CASHIER_SKIP_BROWSER_WARNING'] = '1'
            try:
                return test_client.main([base, key, str(args.video), '--output-dir', str(ROOT / '.test-artifacts/evidence')])
            finally:
                if previous is None:
                    os.environ.pop('CASHIER_SKIP_BROWSER_WARNING', None)
                else:
                    os.environ['CASHIER_SKIP_BROWSER_WARNING'] = previous
        return 0
    except (requests.RequestException, OSError, ValueError, KeyError, TypeError):
        print('Ошибка проверки: проверьте доступность туннеля, состояние сервиса и локальную конфигурацию.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
