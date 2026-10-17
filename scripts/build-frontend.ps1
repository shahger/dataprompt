param()
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$source = Join-Path $project 'frontend/forte-cashier-guard-main'
$target = Join-Path $project 'static'
if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Установите Node.js LTS с npm, откройте новый PowerShell и повторите сборку.'
}
Push-Location $source
try {
    if (Test-Path -LiteralPath 'package-lock.json') { & npm ci --cache (Join-Path $project '.npm-cache') --no-audit --no-fund }
    else { & npm install --cache (Join-Path $project '.npm-cache') --no-audit --no-fund }
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить зависимости интерфейса.' }
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Сборка интерфейса завершилась ошибкой.' }
    $dist = Join-Path $source 'dist'
    if (-not (Test-Path -LiteralPath (Join-Path $dist 'index.html'))) { throw 'Не найден результат сборки dist/index.html.' }
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    $legacy = Join-Path $target 'index.legacy.html'
    if (-not (Test-Path -LiteralPath $legacy) -and (Test-Path -LiteralPath (Join-Path $target 'index.html'))) {
        Copy-Item -LiteralPath (Join-Path $target 'index.html') -Destination $legacy
    }
    # Only replace the generated asset folder within this project's static directory.
    $assets = Join-Path $target 'assets'
    $expected = [IO.Path]::GetFullPath((Join-Path $project 'static/assets'))
    if ([IO.Path]::GetFullPath($assets) -ne $expected -or -not $expected.StartsWith([IO.Path]::GetFullPath($project) + [IO.Path]::DirectorySeparatorChar)) {
        throw 'Небезопасный путь каталога ресурсов.'
    }
    if (Test-Path -LiteralPath $assets) { Remove-Item -LiteralPath $assets -Recurse -Force }
    Copy-Item -Path (Join-Path $dist '*') -Destination $target -Recurse -Force
    Write-Host 'Интерфейс собран в static/. Node.js не требуется в Docker-образе.'
} finally { Pop-Location }
