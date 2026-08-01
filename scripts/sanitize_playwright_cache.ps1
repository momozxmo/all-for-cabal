param(
    [Parameter(Mandatory = $true)]
    [string]$BuildCache
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$buildCachePath = [IO.Path]::GetFullPath($BuildCache).TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
)
if ([IO.Path]::GetFileName($buildCachePath) -ne 'build-cache') {
    throw "Refusing to sanitize a browser cache outside a build-cache directory: $buildCachePath"
}

$browserCachePath = Join-Path $buildCachePath 'ms-playwright'
if (-not (Test-Path -LiteralPath $browserCachePath)) {
    throw "Playwright browser cache does not exist: $browserCachePath"
}

$browserCacheItem = Get-Item -LiteralPath $browserCachePath -Force
if ($browserCacheItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw "Refusing to sanitize a reparse-point browser cache: $browserCachePath"
}

Get-ChildItem -LiteralPath $browserCachePath -Recurse -File -Filter '*.log' |
    Remove-Item -Force
