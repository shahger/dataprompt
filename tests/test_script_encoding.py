"""PowerShell 5.1 needs the UTF-8 BOM to read Russian script text correctly."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / 'scripts').glob('*.ps1'))


@pytest.mark.parametrize('script', SCRIPTS, ids=lambda path: path.name)
def test_powershell_utf8_bom(script):
    raw = script.read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf'), f'{script.name}: UTF-8 BOM required'
    raw.decode('utf-8-sig')


@pytest.mark.parametrize('script', SCRIPTS, ids=lambda path: path.name)
def test_windows_powershell_51_parser(script):
    executable = shutil.which('powershell.exe')
    if not executable:
        pytest.skip('Windows PowerShell is unavailable on this platform')
    literal = str(script).replace("'", "''")
    command = "$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile('" + literal + "',[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { exit 1 }"
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, timeout=20)
    assert result.returncode == 0, f'{script.name}: Windows PowerShell parse error'
