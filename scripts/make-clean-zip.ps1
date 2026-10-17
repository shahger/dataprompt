param([string]$Out = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'dataprompt-clean.zip'))
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$python = Join-Path $project '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
& $python -X utf8 (Join-Path $project 'tools/handover.py') archive --out $Out
exit $LASTEXITCODE
