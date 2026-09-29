[CmdletBinding()]
param([string]$Current)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$currentPath = if ([string]::IsNullOrWhiteSpace($Current)) {
    Join-Path $repositoryRoot 'contracts\generated\openapi.yaml'
} else {
    (Resolve-Path -LiteralPath $Current).Path
}
$toolExtension = if ($env:OS -eq 'Windows_NT') { '.cmd' } else { '' }
$redocly = Join-Path $PSScriptRoot ('node_modules\.bin\redocly' + $toolExtension)
$temporaryJson = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-local-first-' + [System.Guid]::NewGuid().ToString('N') + '.json'
)

function Get-Property($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    return $Object.PSObject.Properties[$Name].Value
}

function Assert-Property($Object, [string]$Name, [string]$Context) {
    if ($null -eq (Get-Property $Object $Name)) {
        throw "Missing local-first property '$Name' on $Context."
    }
}

try {
    if (-not (Test-Path -LiteralPath $redocly)) {
        throw 'Missing Redocly CLI. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
    }
    & $redocly 'bundle' $currentPath '--output' $temporaryJson '--ext' 'json'
    if ($LASTEXITCODE -ne 0) { throw 'Could not bundle local-first contract.' }
    $document = Get-Content -Raw -LiteralPath $temporaryJson | ConvertFrom-Json -Depth 100

    $status = Get-Property $document.components.schemas 'AppAuthStatus'
    Assert-Property $status.properties 'server_instance_id' 'AppAuthStatus'
    Assert-Property $status.properties 'owner_scope_id' 'AppAuthStatus'

    $upload = Get-Property $document.components.schemas 'UploadCreateRequest'
    Assert-Property $upload.properties 'target_asset_id' 'UploadCreateRequest'

    $asset = Get-Property $document.components.schemas 'Asset'
    Assert-Property $asset.properties 'content_sha256' 'Asset'
    Assert-Property $asset.properties 'durable_client_copy_confirmed' 'Asset'
    Assert-Property $asset.properties 'cleanup_after' 'Asset'

    $ack = Get-Property $document.components.schemas 'AssetLocalCopyAcknowledgement'
    Assert-Property $ack.properties 'client_asset_id' 'AssetLocalCopyAcknowledgement'
    Assert-Property $ack.properties 'sha256' 'AssetLocalCopyAcknowledgement'

    $path = Get-Property $document.paths '/api/v1/assets/{asset_id}/local-copy'
    $operation = Get-Property $path 'put'
    if ($null -eq $operation -or $operation.operationId -ne 'confirmAssetLocalCopy') {
        throw 'Missing confirmAssetLocalCopy PUT operation.'
    }
    $schemes = @($operation.security | ForEach-Object { $_.PSObject.Properties.Name })
    if ('AppBearer' -notin $schemes) {
        throw 'confirmAssetLocalCopy must require AppBearer.'
    }

    Write-Output 'Local-first asset contract boundary verification passed.'
}
finally {
    if (Test-Path -LiteralPath $temporaryJson) {
        Remove-Item -LiteralPath $temporaryJson -Force -ErrorAction SilentlyContinue
    }
}
