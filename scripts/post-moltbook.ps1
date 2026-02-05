# Post to Moltbook from the host (workaround when the agent won't use exec).
# Usage: .\scripts\post-moltbook.ps1 -Title "Your title" -Content "Your content"
# Optional: -Submolt "bitcoin" (default)

param(
    [Parameter(Mandatory = $true)]
    [string]$Title,
    [Parameter(Mandatory = $true)]
    [string]$Content,
    [string]$Submolt = "bitcoin"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $projectRoot) { $projectRoot = (Get-Location).Path }
$envPath = Join-Path $projectRoot "config\.env"
if (-not (Test-Path $envPath)) {
    Write-Error "config\.env not found. Add MOLTBOOK_API_TOKEN there."
    exit 1
}
$token = $null
Get-Content $envPath | ForEach-Object {
    if ($_ -match '^\s*MOLTBOOK_API_TOKEN\s*=\s*(.+)\s*$') { $token = $matches[1].Trim().Trim('"').Trim("'") }
}
if (-not $token) {
    Write-Error "MOLTBOOK_API_TOKEN not found in config\.env"
    exit 1
}

$body = @{ submolt = $Submolt; title = $Title; content = $Content } | ConvertTo-Json -Compress
$headers = @{ "Content-Type" = "application/json"; "Authorization" = "Bearer $token" }
Write-Host "Posting to m/$Submolt : $Title"
try {
    $result = Invoke-RestMethod -Uri "https://www.moltbook.com/api/v1/posts" -Method POST -Headers $headers -Body $body
    if ($result.success) {
        Write-Host "Post created." -ForegroundColor Green
        if ($result.post) { Write-Host "URL: $($result.post.url)" }
    } else {
        Write-Host "Response: $result"
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    if ($_.Exception.Response) { Write-Host $_.Exception.Response.StatusCode }
}
