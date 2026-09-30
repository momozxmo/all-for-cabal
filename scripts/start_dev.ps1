$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Run scripts\setup_dev.ps1 first.'
}
# The existing launcher uses port 8000 and a single-instance mutex. Never reuse
# an installed application's server when the user intended to run source code.
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8000 is occupied. Save work and close the installed app/server before starting development.'
}

$previousAppData = $env:LOCALAPPDATA
$previousBrowserCache = $env:PLAYWRIGHT_BROWSERS_PATH
Push-Location $projectRoot
try {
    $env:LOCALAPPDATA = Join-Path $projectRoot '.local-runtime\developer-appdata'
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $projectRoot 'build-cache\ms-playwright'
    Write-Host "Developer data only: $env:LOCALAPPDATA\AllForCabalWeb"
    & $venvPython -X utf8 -m local_app.launcher
    if ($LASTEXITCODE -ne 0) { throw 'Developer launcher failed. Check the developer runtime logs.' }
}
finally {
    $env:LOCALAPPDATA = $previousAppData
    $env:PLAYWRIGHT_BROWSERS_PATH = $previousBrowserCache
    Pop-Location
}
