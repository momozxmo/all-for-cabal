param(
    [ValidateSet('start', 'test', 'logs', 'stop')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envFile = Join-Path $projectRoot '.env.docker.local'

function Find-DockerCli {
    $command = Get-Command docker -CommandType Application `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    $candidate = Join-Path $env:LOCALAPPDATA `
        'Programs\DockerDesktop\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    throw 'Docker CLI was not found. Start or reinstall Docker Desktop.'
}

function Invoke-Docker([string[]]$Arguments) {
    & $script:DockerCli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code $LASTEXITCODE"
    }
}

function New-RandomBase64Url([int]$ByteCount) {
    $bytes = [byte[]]::new($ByteCount)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Ensure-DockerEnvironment {
    if (Test-Path -LiteralPath $envFile) {
        return
    }

    $lines = @(
        "APP_SECRET_KEY=$(New-RandomBase64Url 48)",
        "AZTEK_SESSION_ENCRYPTION_KEY=$(New-RandomBase64Url 32)",
        'BOOTSTRAP_ADMIN_USERNAME=docker-admin',
        "BOOTSTRAP_ADMIN_PASSWORD=$(New-RandomBase64Url 18)"
    )
    [IO.File]::WriteAllLines(
        $envFile,
        $lines,
        [Text.UTF8Encoding]::new($false)
    )
}

function Read-DockerLogin {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $envFile) {
        $key, $value = $line -split '=', 2
        if ($key) {
            $values[$key] = $value
        }
    }
    return $values
}

function Wait-DockerHealth {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            $response = Invoke-RestMethod `
                -Uri 'http://127.0.0.1:8000/api/health' `
                -TimeoutSec 3
            if ($response.ok -eq $true) {
                return
            }
        }
        catch {
            # The service can refuse connections while Uvicorn is starting.
        }
        Start-Sleep -Seconds 1
    }

    & $script:DockerCli compose logs --no-color web
    throw 'Docker service did not become healthy within 60 seconds.'
}

$script:DockerCli = Find-DockerCli
Push-Location $projectRoot
try {
    Invoke-Docker @('info')
    Ensure-DockerEnvironment

    switch ($Action) {
        'start' {
            Invoke-Docker @('compose', 'up', '--build', '-d')
            Wait-DockerHealth
            $login = Read-DockerLogin
            Write-Host 'All for Cabal Web is ready: http://127.0.0.1:8000'
            Write-Host "Username: $($login['BOOTSTRAP_ADMIN_USERNAME'])"
            Write-Host "Password: $($login['BOOTSTRAP_ADMIN_PASSWORD'])"
        }
        'test' {
            Invoke-Docker @('compose', 'build', 'web')
            Invoke-Docker @(
                'compose', 'run', '--rm', '--no-deps', 'web',
                'python', '-B', '-m', 'pytest', '-p',
                'no:cacheprovider', '-q', 'tests'
            )
        }
        'logs' {
            Invoke-Docker @('compose', 'logs', '-f', 'web')
        }
        'stop' {
            Invoke-Docker @('compose', 'down')
        }
    }
}
finally {
    Pop-Location
}
