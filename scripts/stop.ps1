# OpenClaw Bitcoin Agent - Stop Script (PowerShell)
# Usage: .\stop.ps1

Write-Host "Stopping OpenClaw Bitcoin Agent..." -ForegroundColor Cyan

# Navigate to docker directory
$dockerDir = Join-Path $PSScriptRoot "..\docker"
Set-Location $dockerDir

# Stop the container
docker-compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "OpenClaw Bitcoin Agent stopped successfully." -ForegroundColor Green
} else {
    Write-Host "Warning: Container may not have stopped cleanly." -ForegroundColor Yellow
    Write-Host "You can force stop with: docker stop openclaw-bitcoin-agent" -ForegroundColor White
}
