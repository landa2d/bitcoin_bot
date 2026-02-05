# Reset OpenClaw agent session so the next Telegram message starts a new session.
# Use this if the agent never uses the Moltbook queue (e.g. keeps suggesting curl)
# so that the skill list is rebuilt and may include custom skills.
# Run from repo root. Restart the container after running this script.

$ErrorActionPreference = "Stop"
$sessionsDir = Join-Path $PSScriptRoot "..\data\openclaw\agents\main\sessions"
$sessionsDir = [System.IO.Path]::GetFullPath($sessionsDir)

if (-not (Test-Path $sessionsDir)) {
    Write-Error "Sessions directory not found: $sessionsDir"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
Get-ChildItem -Path $sessionsDir -Filter "*.jsonl" | ForEach-Object {
    $newName = "$($_.Name).$timestamp.bak"
    Rename-Item -Path $_.FullName -NewName $newName -Force
    Write-Host "Backed up: $($_.Name) -> $newName"
}

$sessionsJson = Join-Path $sessionsDir "sessions.json"
if (Test-Path $sessionsJson) {
    Copy-Item -Path $sessionsJson -Destination "$sessionsJson.$timestamp.bak" -Force
    Write-Host "Backed up: sessions.json -> sessions.json.$timestamp.bak"
}
@{} | ConvertTo-Json | Set-Content -Path $sessionsJson -Encoding UTF8
Write-Host "Reset sessions.json (empty)."

Write-Host ""
Write-Host "Session reset complete. Restart the container so the next Telegram message starts a new session:"
Write-Host "  .\scripts\stop.ps1"
Write-Host "  .\scripts\start.ps1"
