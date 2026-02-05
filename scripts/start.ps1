# OpenClaw Bitcoin Agent - Start Script (PowerShell)
# Usage: .\start.ps1

Write-Host "Starting OpenClaw Bitcoin Agent..." -ForegroundColor Cyan

# Check if Docker is running
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if .env file exists
$envPath = Join-Path $PSScriptRoot "..\config\.env"
if (-not (Test-Path $envPath)) {
    Write-Host "ERROR: .env file not found at $envPath" -ForegroundColor Red
    Write-Host "Please copy config\env.example to config\.env and fill in your API keys." -ForegroundColor Yellow
    exit 1
}

# Navigate to docker directory
$dockerDir = Join-Path $PSScriptRoot "..\docker"
Set-Location $dockerDir

# Start the container (skip build to avoid upstream TypeScript issues)
# To rebuild the image manually, run: docker-compose build --no-cache
Write-Host "Starting container..." -ForegroundColor Yellow
docker-compose up -d --no-build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "OpenClaw Bitcoin Agent is now running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Cyan
    Write-Host "  View logs:    .\scripts\logs.ps1" -ForegroundColor White
    Write-Host "  Stop agent:   .\stop.ps1 (or docker-compose down)" -ForegroundColor White
    Write-Host "  Shell access: docker exec -it openclaw-bitcoin-agent /bin/bash" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "ERROR: Failed to start container." -ForegroundColor Red
    exit 1
}
