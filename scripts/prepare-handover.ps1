param([switch]$AllowStub, [switch]$Finalize)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$python = Join-Path $project '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
$docExit = 0
if ($Finalize) {
    & (Join-Path $PSScriptRoot 'finalize-jury-doc.ps1')
    $docExit = $LASTEXITCODE
}
$arguments = @((Join-Path $project 'tools/handover.py'), 'preflight')
if ($AllowStub) { $arguments += '--allow-stub' }
& $python -X utf8 @arguments
if ($LASTEXITCODE -ne 0 -or $docExit -ne 0) { exit 1 }
exit 0
