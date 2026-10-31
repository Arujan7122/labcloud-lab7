$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    & '.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
}
$env:APP_ENV = 'development'
$env:STORAGE_BACKEND = 'database'
$env:HOST = '127.0.0.1'
$env:PORT = '8000'
& '.venv\Scripts\python.exe' app.py
