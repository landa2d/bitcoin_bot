# OpenClaw Bitcoin Agent - View Logs Script (PowerShell)
# Usage: .\logs.ps1

Write-Host "Streaming logs from OpenClaw Bitcoin Agent..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Navigate to docker directory
$dockerDir = Join-Path $PSScriptRoot "..\docker"
Set-Location $dockerDir

# Stream logs
docker-compose logs -f --tail=100
