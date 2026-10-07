[CmdletBinding()]
param(
    [switch]$SkipContract
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Invoke-RepositoryCommand([string]$Command) {
    Write-Output "==> $Command"
    & pwsh -NoProfile -Command $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command"
    }
}

Push-Location $repositoryRoot
try {
    if (-not $SkipContract) {
        & pwsh -NoProfile -File (Join-Path $repositoryRoot 'contracts\tooling\verify-generated.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Generated contract verification failed.' }
        & pwsh -NoProfile -File (Join-Path $repositoryRoot 'contracts\tooling\verify-contract.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Contract verification failed.' }
    }
    Invoke-RepositoryCommand 'corepack pnpm@10.34.5 web:lint'
    Invoke-RepositoryCommand 'corepack pnpm@10.34.5 web:typecheck'
    Invoke-RepositoryCommand 'corepack pnpm@10.34.5 web:test'
    Invoke-RepositoryCommand 'corepack pnpm@10.34.5 web:build'
    Invoke-RepositoryCommand 'corepack pnpm@10.34.5 --filter @clothes-model/web-admin check:bundle'
}
finally {
    Pop-Location
}

Write-Output 'PHASE 7 WEB ADMIN AND OPERATIONS GATE PASSED'
Write-Output 'Run corepack pnpm@10.34.5 web:test:e2e separately when a browser and the contract mock are available.'
