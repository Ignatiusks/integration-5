$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
foreach ($name in @('postgres_password','jwt_secret','login_password','grafana_password')) {
    $path = Join-Path $PSScriptRoot "secrets/$name.txt"
    if (!(Test-Path $path)) {
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($bytes)
        $rng.Dispose()
        [IO.File]::WriteAllText($path, [Convert]::ToBase64String($bytes))
    }
}
docker run --rm -v "${PSScriptRoot}:/app" -w /app ghcr.io/astral-sh/uv:0.7.13-python3.12-bookworm-slim uv lock
if ($LASTEXITCODE -ne 0) { throw 'uv lock failed' }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Compose failed' }
