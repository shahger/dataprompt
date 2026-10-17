param()
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$python = Join-Path $project '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
& $python -X utf8 (Join-Path $project 'tools/handover.py') status
$checkExit = $LASTEXITCODE
$sessionFile = Join-Path $project '.public-session.json'
if (Test-Path -LiteralPath $sessionFile) {
    try {
        $session = Get-Content -LiteralPath $sessionFile -Raw | ConvertFrom-Json
        $process = Get-Process -Id $session.pid -ErrorAction SilentlyContinue
        $alive = $process -and $process.StartTime.ToUniversalTime().Ticks -eq [long]$session.startedTicks -and $process.Path -eq $session.executable
        Write-Host ('Записанный процесс ngrok активен: ' + [bool]$alive)
    } catch { Write-Host 'Запись процесса ngrok недоступна; процесс не изменён.' }
} else { Write-Host 'Файл состояния ngrok отсутствует; процесс не изменён.' }
exit $checkExit
