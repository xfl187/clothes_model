[CmdletBinding()]
param(
    [string]$Current
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$currentPath = if ([string]::IsNullOrWhiteSpace($Current)) {
    Join-Path $repositoryRoot 'contracts\generated\openapi.yaml'
}
else {
    (Resolve-Path -LiteralPath $Current).Path
}
$toolExtension = if ($env:OS -eq 'Windows_NT') { '.cmd' } else { '' }
$redocly = Join-Path $PSScriptRoot ('node_modules\.bin\redocly' + $toolExtension)
$temporaryJson = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-phase2-contract-' + [System.Guid]::NewGuid().ToString('N') + '.json'
)

function Get-Property($Object, [string]$Name) {
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name]) {
        return $null
    }
    return $Object.PSObject.Properties[$Name].Value
}

function Get-Operation($Document, [string]$Path, [string]$Method) {
    $pathItem = Get-Property $Document.paths $Path
    $operation = Get-Property $pathItem $Method
    if ($null -eq $operation) {
        throw "Missing Phase 2 contract operation: $($Method.ToUpperInvariant()) $Path"
    }
    return $operation
}

function Get-SecuritySignatures($Security) {
    if ($null -eq $Security) {
        return @('<inherited>')
    }
    return @(
        $Security | ForEach-Object {
            ($_.PSObject.Properties.Name | Sort-Object) -join '+'
        } | Sort-Object
    )
}

function Assert-Operation(
    $Document,
    [string]$Path,
    [string]$Method,
    [string[]]$Security,
    [string[]]$Responses
) {
    $operation = Get-Operation $Document $Path $Method
    $actualSecurity = Get-SecuritySignatures $operation.security
    $expectedSecurity = @($Security | Sort-Object)
    if (($actualSecurity -join "`n") -ne ($expectedSecurity -join "`n")) {
        throw (
            "Unexpected security for $($Method.ToUpperInvariant()) $Path. " +
            "Expected=$($expectedSecurity -join ',') Actual=$($actualSecurity -join ',')"
        )
    }
    foreach ($status in $Responses) {
        if ($null -eq $operation.responses.PSObject.Properties[$status]) {
            throw "Missing response $status on $($Method.ToUpperInvariant()) $Path."
        }
    }
}

try {
    if (-not (Test-Path -LiteralPath $redocly)) {
        throw 'Missing Redocly CLI. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
    }
    & $redocly 'bundle' $currentPath '--output' $temporaryJson '--ext' 'json'
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not bundle the Phase 2 contract for boundary verification.'
    }
    $document = Get-Content -Raw -LiteralPath $temporaryJson | ConvertFrom-Json -Depth 100

    Assert-Operation $document '/api/v1/auth/status' 'get' @('AppBearer') @('200', '401', '403')
    Assert-Operation $document '/api/v1/admin/auth/session' 'get' @('AdminSession') @('200', '401', '403')
    Assert-Operation $document '/api/v1/admin/auth/session' 'post' @() @('201', '401', '429')
    Assert-Operation $document '/api/v1/admin/auth/session' 'delete' @('AdminCsrf+AdminSession') @('204', '401', '403')

    Assert-Operation $document '/api/v1/uploads' 'post' @('AppBearer') @('201', '401', '409', '507')
    Assert-Operation $document '/api/v1/uploads/{upload_id}' 'get' @('AppBearer') @('200', '401', '403', '404')
    Assert-Operation $document '/api/v1/uploads/{upload_id}' 'delete' @('AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/uploads/{upload_id}/content' 'patch' @('AppBearer') @('200', '401', '409', '507')
    Assert-Operation $document '/api/v1/uploads/{upload_id}/complete' 'post' @('AppBearer') @('201', '401', '409', '422', '507')

    Assert-Operation $document '/api/v1/assets' 'get' @('AppBearer') @('200', '401', '403')
    Assert-Operation $document '/api/v1/assets/{asset_id}' 'get' @('AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/assets/{asset_id}' 'patch' @('AppBearer') @('200', '401', '403', '404', '422')
    Assert-Operation $document '/api/v1/assets/{asset_id}/content' 'get' @('AdminSession', 'AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/assets/{asset_id}/content' 'delete' @('AppBearer') @('200', '401', '403', '404', '409')
    Assert-Operation $document '/api/v1/assets/{asset_id}/references' 'get' @('AppBearer') @('200', '401', '403', '404')

    foreach ($schema in @(
        'AdminSession',
        'AssetUpdateRequest',
        'AssetContentDeletionResult',
        'AssetReference',
        'AssetReferencePage'
    )) {
        if ($null -eq $document.components.schemas.PSObject.Properties[$schema]) {
            throw "Missing Phase 2 shared schema: $schema"
        }
    }

    Write-Output 'Phase 2 security and response boundary verification passed.'
}
finally {
    if (Test-Path -LiteralPath $temporaryJson) {
        Remove-Item -LiteralPath $temporaryJson -Force -ErrorAction SilentlyContinue
    }
}
