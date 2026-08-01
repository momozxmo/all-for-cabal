param(
    [string]$Version = '0.1.0'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$browserCache = Join-Path $projectRoot 'build-cache\ms-playwright'
$pytestTemp = Join-Path $projectRoot 'build-cache\pytest'
$setupName = "All for Cabal Web Setup-$Version.exe"
$setupPath = Join-Path $projectRoot "artifacts\$setupName"

$isccCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
)
$iscc = $isccCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1
if (-not $iscc) {
    $messageBytes = [Convert]::FromBase64String(
        '4LmE4Lih4LmI4Lie4LiaIElubm8gU2V0dXAgNiDguIHguKPguLjguJPguLLguJXguLTguJTguJXguLHguYnguIfguIjguLLguIEganJzb2Z0d2FyZS5vcmcg4LiB4LmI4Lit4LiZIGJ1aWxk'
    )
    throw [Text.Encoding]::UTF8.GetString($messageBytes)
}

Push-Location $projectRoot
try {
    python -m pip install -r requirements.txt -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }

    $env:PLAYWRIGHT_BROWSERS_PATH = $browserCache
    & (Join-Path $PSScriptRoot 'reset_playwright_cache.ps1') `
        -BuildCache (Join-Path $projectRoot 'build-cache')
    python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium download failed' }

    python -m pytest -q tests --basetemp=$pytestTemp
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped' }

    & (Join-Path $PSScriptRoot 'sanitize_playwright_cache.ps1') `
        -BuildCache (Join-Path $projectRoot 'build-cache')
    python -m PyInstaller --noconfirm --clean local_web.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
    python -m local_app.release_verify 'dist\All for Cabal Web'
    if ($LASTEXITCODE -ne 0) { throw 'Release tree verification failed' }

    & $iscc "/DMyAppVersion=$Version" 'installer\AllForCabalWeb.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed' }
    if (-not (Test-Path -LiteralPath $setupPath)) {
        throw "Expected Setup was not created: $setupPath"
    }

    python -m local_app.release_verify artifacts --checksum $setupPath
    if ($LASTEXITCODE -ne 0) { throw 'Release verification or checksum failed' }
    Write-Host "Team installer: $setupPath"
    Write-Host "SHA-256: $setupPath.sha256"
}
finally {
    Pop-Location
}
