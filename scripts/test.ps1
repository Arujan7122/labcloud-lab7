$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
& '.venv\Scripts\python.exe' -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.venv\Scripts\python.exe' -m pytest -v
exit $LASTEXITCODE
