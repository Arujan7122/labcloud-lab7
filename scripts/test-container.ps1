$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
docker info | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first' }
docker build -t labcloud:1.0 .
if ($LASTEXITCODE -ne 0) { throw 'Image build failed' }
docker run -d --name labcloud-lab -p 127.0.0.1:8000:8000 -e APP_ENV=container --cap-drop ALL --security-opt no-new-privileges labcloud:1.0
if ($LASTEXITCODE -ne 0) { throw 'Container startup failed' }
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8000/health'
            if ($health.status -eq 'healthy') { $ready = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'Container did not become healthy' }
    docker ps --filter name=labcloud-lab
    docker exec labcloud-lab id
    & '.venv\Scripts\python.exe' scripts/verify_http.py --url http://127.0.0.1:8000 --count 75 --output evidence/docker-http.json
    if ($LASTEXITCODE -ne 0) { throw 'Container HTTP verification failed' }
} finally {
    docker logs labcloud-lab 2>&1 | Out-File -Encoding utf8 evidence/docker.log
    docker stop labcloud-lab | Out-Null
    docker rm labcloud-lab | Out-Null
}
