param()
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$sessionFile = Join-Path $project '.public-session.json'
if (Test-Path -LiteralPath $sessionFile) {
    $owned = Get-Content -LiteralPath $sessionFile -Raw | ConvertFrom-Json
    $process = Get-Process -Id $owned.pid -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq [long]$owned.startedTicks -and $process.Path -eq $owned.executable) {
        Stop-Process -Id $process.Id
        Write-Host 'Туннель ngrok остановлен.'
    } else { Write-Host 'Записанный процесс уже завершён; другие процессы не затронуты.' }
    Remove-Item -LiteralPath $sessionFile -Force
} else { Write-Host 'Туннель этого скрипта не найден. Туннель, запущенный вручную, остановите в его окне сочетанием Ctrl+C.' }
Push-Location $project
try {
    & docker compose down
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось остановить Docker Compose.' }
    Write-Host 'Контейнеры остановлены. Данные Postgres сохранены.'
} finally { Pop-Location }
