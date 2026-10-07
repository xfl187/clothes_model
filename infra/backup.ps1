param(
    [Parameter(Mandatory)] [string]$DatabasePath,
    [Parameter(Mandatory)] [string]$StoragePath,
    [Parameter(Mandatory)] [string]$OutputPath,
    [string]$Python = (Join-Path $PSScriptRoot '..\backend\.venv\Scripts\python.exe')
)

# Captures a consistent SQLite snapshot (online backup API, safe under active
# writers) plus the private-storage directory into a single operator-owned
# archive. Never place the output inside source control.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $DatabasePath)) {
    throw "Database not found: $DatabasePath"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python interpreter not found: $Python. Pass -Python explicitly."
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-backup-' + [System.Guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Force -Path $staging | Out-Null
try {
    $snapshot = Join-Path $staging 'app.db'
    & $Python -c "import sqlite3,sys; src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close()" $DatabasePath $snapshot
    if ($LASTEXITCODE -ne 0) { throw 'SQLite consistent snapshot failed.' }

    $storageTarget = Join-Path $staging 'storage'
    if (Test-Path -LiteralPath $StoragePath) {
        Copy-Item -LiteralPath $StoragePath -Destination $storageTarget -Recurse
    } else {
        New-Item -ItemType Directory -Force -Path $storageTarget | Out-Null
    }

    $manifest = [ordered]@{
        created_at = (Get-Date).ToUniversalTime().ToString('o')
        database   = 'app.db'
        storage    = 'storage'
    } | ConvertTo-Json
    Set-Content -LiteralPath (Join-Path $staging 'manifest.json') -Value $manifest -Encoding utf8

    $parent = Split-Path -Parent $OutputPath
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $OutputPath -Force
}
finally {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "Backup written to $OutputPath"
