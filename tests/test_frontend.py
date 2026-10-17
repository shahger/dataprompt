"""Built assets must be local, and SPA fallback must not swallow API errors."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMESPACES = ('http://www.w3.org/2000/svg', 'http://www.w3.org/1998/Math/MathML',
              'http://www.w3.org/1999/xlink', 'http://www.w3.org/XML/1998/namespace',
              'http://www.w3.org/1999/xhtml')


def test_built_assets_have_no_external_resources():
    files = [p for p in (ROOT / 'static').rglob('*') if p.suffix in {'.html', '.js', '.css'}]
    assert files
    for path in files:
        content = path.read_text(encoding='utf-8-sig')
        # React embeds harmless namespace identifiers. Everything else, including
        # external links hidden in JS literals or CSS url(), fails this scan.
        for namespace in NAMESPACES:
            content = content.replace(namespace, '')
        assert not re.search(r'https?://', content, re.IGNORECASE), f'external reference in {path.name}'
        assert not re.search(r'''(?:src|href)\s*=\s*["']\s*//|url\(\s*["']?\s*//''', content, re.IGNORECASE), path.name
    index = (ROOT / 'static/index.html').read_text(encoding='utf-8-sig')
    assert 'lang="ru"' in index
    assert 'Контроль кассовой дисциплины' in index
    assert (ROOT / 'static/index.legacy.html').exists()


@pytest.mark.parametrize('path', ['/review/session/one', '/workspace'])
def test_spa_deep_link(service, path):
    _, client, _ = service
    assert client.get(path).status_code == 200
    assert client.get(path).text == client.get('/').text


@pytest.mark.parametrize('path', ['/api/missing', '/api/v1/missing', '/ui/api/missing', '/health/missing', '/assets/missing.js'])
def test_spa_does_not_shadow_reserved_paths(service, path):
    _, client, _ = service
    assert client.get(path).status_code == 404
