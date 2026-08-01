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
    throw "Refusing to reset a browser cache outside a build-cache directory: $buildCachePath"
}

$browserCachePath = Join-Path $buildCachePath 'ms-playwright'
if (Test-Path -LiteralPath $browserCachePath) {
    $browserCacheItem = Get-Item -LiteralPath $browserCachePath -Force
    if ($browserCacheItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing to reset a reparse-point browser cache: $browserCachePath"
    }
    Remove-Item -LiteralPath $browserCachePath -Recurse -Force
}

New-Item -ItemType Directory -Path $browserCachePath -Force | Out-Null
