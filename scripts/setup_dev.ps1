param([string]$PythonExecutable = 'python')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$previousBrowserCache = $env:PLAYWRIGHT_BROWSERS_PATH

# Validate before creating anything; use the same Python minor as release builds.
& $PythonExecutable -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required. Use -PythonExecutable with its full path.' }

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $PythonExecutable -m venv '.venv'
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    & $venvPython -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.prefix != sys.base_prefix else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'The existing .venv must use Python 3.12.' }

    & $venvPython -X utf8 -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw 'Development dependency installation failed; setup stopped.' }

    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $projectRoot 'build-cache\ms-playwright'
    & $venvPython -X utf8 -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed; run setup again to retry.' }

    Write-Host 'Development environment ready. No installed-app data was changed.'
    Write-Host 'Start: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_dev.ps1'
}
finally {
    $env:PLAYWRIGHT_BROWSERS_PATH = $previousBrowserCache
    Pop-Location
}
