param(
    [string]$BaseUrl = 'https://reverence-culpable-cupping.ngrok-free.dev',
    [string]$Video
)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$localPython = Join-Path $project '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $localPython) { $python = $localPython }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = 'python' }
else { throw 'Нужен Python и зависимости requirements-dev.txt для проверки сервиса.' }
$arguments = @((Join-Path $project 'tools/check_public.py'), '--base-url', $BaseUrl)
if ($Video) { $arguments += @('--video', (Resolve-Path -LiteralPath $Video).Path) }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Проверка публичного сервиса завершилась ошибкой.' }
