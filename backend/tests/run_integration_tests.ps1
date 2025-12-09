param(
    [string]$ComposeFile = "docker-compose.test.yml"
)

Write-Host "Starting Integration Services using $ComposeFile..."
docker compose -f $ComposeFile up -d

Write-Host "Setting env var ECE_USE_DOCKER=1 and running tests..."
$env:ECE_USE_DOCKER = '1'
$env:PYTHONPATH = (Resolve-Path "..").Path
cd (Resolve-Path "$(Split-Path $MyInvocation.MyCommand.Definition -Parent)")
pytest -q --maxfail=1

Write-Host "Tearing down compose..."
docker compose -f $ComposeFile down
