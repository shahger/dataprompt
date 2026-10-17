param(
    [string]$Domain = 'reverence-culpable-cupping.ngrok-free.dev',
    [string]$NgrokPath = 'C:\Users\shakh\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe'
)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$sessionFile = Join-Path $project '.public-session.json'
$Domain = $Domain -replace '^https?://', '' -replace '/$', ''
if ($Domain -notmatch '^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$') { throw 'Укажите доменное имя без пути, параметров и пробелов.' }
$command = Get-Command ngrok -ErrorAction SilentlyContinue
if ($command) { $executable = $command.Source }
elseif (Test-Path -LiteralPath $NgrokPath -PathType Leaf) { $executable = (Resolve-Path -LiteralPath $NgrokPath).Path }
else { throw 'ngrok не найден. Установите ngrok 3.20+ или передайте -NgrokPath. Авторизуйте его отдельно; токен в этот скрипт не передавайте.' }
$versionText = (& $executable version 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $versionText -notmatch '(\d+\.\d+\.\d+)') { throw 'Не удалось определить версию ngrok.' }
if ([version]$Matches[1] -lt [version]'3.20.0') { throw 'Нужен ngrok версии 3.20 или новее. Обновите установленный ngrok.' }
if (Test-Path -LiteralPath $sessionFile) {
    $owned = Get-Content -LiteralPath $sessionFile -Raw | ConvertFrom-Json
    $existing = Get-Process -Id $owned.pid -ErrorAction SilentlyContinue
    if ($existing -and $existing.StartTime.ToUniversalTime().Ticks -eq [long]$owned.startedTicks) {
        throw 'Публичный сервис уже запущен этим скриптом. Сначала выполните scripts/stop-public.ps1.'
    }
}
Push-Location $project
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker не найден. Установите и запустите Docker Desktop.' }
    $dockerCheck = & docker info --format '{{.ServerVersion}}' 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop не готов. Запустите Linux engine и повторите команду.' }
    # Compose reads .env itself. This script never opens or prints it.
    & docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось собрать или запустить Docker Compose.' }
    $ready = $false
    $until = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $until) {
        try {
            $health = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 3
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'Сервис не стал готов за 3 минуты. Проверьте docker compose ps и локальные журналы.' }
    Write-Host "Сервис готов. Запуск туннеля https://$Domain. Не закрывайте этот PowerShell."
    foreach ($flag in @('url', 'domain')) {
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $executable
        $info.Arguments = "http --$flag=$Domain 8000 --log=stdout --log-format=json"
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $info
        if (-not $process.Start()) { throw 'Не удалось запустить ngrok.' }
        # Drain in memory only. Never write ngrok diagnostics/token text to disk or console.
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        @{ pid = $process.Id; startedTicks = $process.StartTime.ToUniversalTime().Ticks; executable = $executable; domain = $Domain } |
            ConvertTo-Json | Set-Content -LiteralPath $sessionFile -Encoding UTF8
        try {
            while (-not $process.WaitForExit(1000)) { }
            $diagnostic = $stdout.GetAwaiter().GetResult() + $stderr.GetAwaiter().GetResult()
            if ($process.ExitCode -eq 0) { break }
            if ($flag -eq 'url' -and $diagnostic -match '(?i)(unknown flag|flag provided but not defined).*url') {
                Write-Host 'Эта версия использует --domain; повторяем запуск.'
                continue
            }
            if ($diagnostic -match '(?i)(ERR_NGROK_4018|ERR_NGROK_105|authtoken|authentication|not authenticated)') {
                throw 'ngrok не авторизован или авторизация недействительна. Настройте его отдельно; не публикуйте токен.'
            }
            throw 'ngrok завершился с ошибкой. Проверьте домен, доступность сети и отсутствие другого туннеля в аккаунте.'
        } finally {
            if (-not $process.HasExited) { $process.Kill() }
            $process.Dispose()
            if (Test-Path -LiteralPath $sessionFile) { Remove-Item -LiteralPath $sessionFile -Force }
        }
    }
} finally { Pop-Location }
