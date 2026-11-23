param([ValidateSet('setup', 'start', 'stop')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $root
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker failed (exit $LASTEXITCODE)." }
}
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Install Docker Desktop for Windows, enable WSL 2, then restart this script.'
    }
    Invoke-Docker info --format '{{.OSType}}'
    if ($Action -eq 'stop') {
        Invoke-Docker compose -p goldnam-local stop
        Write-Host 'Stopped. Local database is preserved.'
        exit 0
    }
    if ($Action -eq 'setup') {
        Invoke-Docker compose -p goldnam-local build
        Invoke-Docker compose -p goldnam-local run --rm --no-deps --user root --volume "${root}:/local" app python /local/scripts/setup_local.py
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root '.env'))) {
        throw 'Run 01-Setup.cmd first to choose your app password.'
    }
    Invoke-Docker compose -p goldnam-local up -d
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $health = Invoke-RestMethod 'http://localhost:10000/api/v1/health' -TimeoutSec 3
            $ready = $true
            break
        } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw 'App did not respond. Check: docker compose -p goldnam-local logs --tail 50 app' }
    if (-not $health.data.auth_configured -or -not $health.data.database_configured) {
        throw 'App configuration is incomplete. Check local .env and run setup again.'
    }
    Write-Host 'Goldnam Sachs: http://localhost:10000 (use Chrome or Edge)'
    Start-Process 'http://localhost:10000'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
