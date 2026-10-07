[CmdletBinding()]
param(
    [string]$Python = (Join-Path $PSScriptRoot '..\backend\.venv\Scripts\python.exe')
)

# Deterministic backup/restore verification. Builds a live-shaped source (a
# migrated database plus private storage), backs it up, restores into a clean
# target, and asserts the pair is intact.
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonPath = [System.IO.Path]::GetFullPath($Python)
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python interpreter not found: $pythonPath"
}

$workspace = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-backup-verify-' + [System.Guid]::NewGuid().ToString('N')
)
$sourceRoot = Join-Path $workspace 'source'
$targetRoot = Join-Path $workspace 'target'
$archive = Join-Path $workspace 'backup.zip'
New-Item -ItemType Directory -Force -Path (Join-Path $sourceRoot 'storage') | Out-Null

$env:PYTHONPATH = Join-Path $repositoryRoot 'backend\src'
try {
    $sourceDb = Join-Path $sourceRoot 'app.db'
    & $pythonPath -c "import sys; from pathlib import Path; from clothes_model.infrastructure.database.migrations import upgrade_database; upgrade_database(sys.argv[1], Path(sys.argv[2]))" "sqlite+aiosqlite:///$($sourceDb -replace '\\','/')" (Join-Path $sourceRoot 'migration.lock')
    if ($LASTEXITCODE -ne 0) { throw 'Source database migration failed.' }

    Set-Content -LiteralPath (Join-Path $sourceRoot 'storage\marker.bin') -Value 'private-content' -NoNewline

    & (Join-Path $PSScriptRoot 'backup.ps1') `
        -DatabasePath $sourceDb `
        -StoragePath (Join-Path $sourceRoot 'storage') `
        -OutputPath $archive `
        -Python $pythonPath
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed.' }

    & (Join-Path $PSScriptRoot 'restore.ps1') `
        -ArchivePath $archive `
        -DatabasePath (Join-Path $targetRoot 'app.db') `
        -StoragePath (Join-Path $targetRoot 'storage')
    if ($LASTEXITCODE -ne 0) { throw 'Restore failed.' }

    $targetDb = Join-Path $targetRoot 'app.db'
    $checkScript = @'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
tables = conn.execute(
    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
).fetchone()[0]
version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
conn.close()
assert tables > 10, tables
assert version is not None
'@
    $checkPath = Join-Path $workspace 'check.py'
    Set-Content -LiteralPath $checkPath -Value $checkScript -Encoding utf8
    & $pythonPath $checkPath $targetDb
    if ($LASTEXITCODE -ne 0) { throw 'Restored database integrity check failed.' }

    $marker = Join-Path $targetRoot 'storage\marker.bin'
    if (-not (Test-Path -LiteralPath $marker)) { throw 'Restored storage marker is missing.' }
    if ((Get-Content -LiteralPath $marker -Raw) -ne 'private-content') {
        throw 'Restored storage content does not match.'
    }

    Write-Output 'PHASE 8 BACKUP/RESTORE VERIFICATION PASSED'
}
finally {
    Remove-Item -LiteralPath $workspace -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
}
