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
    'clothes-model-phase6-contract-' + [System.Guid]::NewGuid().ToString('N') + '.json'
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
        throw "Missing Phase 6 contract operation: $($Method.ToUpperInvariant()) $Path"
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
    [string[]]$Responses,
    [switch]$Idempotent
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
    if ($Idempotent) {
        $hasKey = @(
            $operation.parameters | Where-Object {
                (Get-Property $_ 'name') -eq 'Idempotency-Key' -or
                ((Get-Property $_ '$ref') -like '*IdempotencyKey')
            }
        ).Count -gt 0
        if (-not $hasKey) {
            throw "Missing Idempotency-Key on $($Method.ToUpperInvariant()) $Path."
        }
    }
}

function Assert-Schema($Document, [string]$Name) {
    if ($null -eq $Document.components.schemas.PSObject.Properties[$Name]) {
        throw "Missing Phase 6 shared schema: $Name"
    }
    return (Get-Property $Document.components.schemas $Name)
}

function Assert-SchemaProperties($Schema, [string]$Name, [string[]]$Expected) {
    foreach ($property in $Expected) {
        if ($null -eq $Schema.properties.PSObject.Properties[$property]) {
            throw "Missing property '$property' on schema '$Name'."
        }
    }
}

function Assert-EnumContains($Schema, [string]$Name, [string[]]$Expected) {
    $actual = @($Schema.enum | ForEach-Object { [string]$_ })
    foreach ($value in $Expected) {
        if ($value -notin $actual) {
            throw "Enum '$Name' is missing Phase 6 value '$value'."
        }
    }
}

function Assert-IdentifierProperty($Schema, [string]$Name, [string]$Property) {
    $value = Get-Property $Schema.properties $Property
    if ($null -eq $value) {
        throw "Missing property '$Property' on schema '$Name'."
    }
    $format = Get-Property $value 'format'
    $reference = Get-Property $value '$ref'
    if ($format -ne 'uuid' -and $reference -notlike '*/Identifier') {
        throw "Property '$Property' on '$Name' must be a UUID resource identifier."
    }
}

try {
    if (-not (Test-Path -LiteralPath $redocly)) {
        throw 'Missing Redocly CLI. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
    }
    & $redocly 'bundle' $currentPath '--output' $temporaryJson '--ext' 'json'
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not bundle the Phase 6 contract for boundary verification.'
    }
    $document = Get-Content -Raw -LiteralPath $temporaryJson | ConvertFrom-Json -Depth 100

    Assert-Operation $document '/api/v1/assets' 'get' `
        @('AppBearer') @('200', '401', '403')
    Assert-Operation $document '/api/v1/assets/{asset_id}' 'get' `
        @('AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/assets/{asset_id}' 'patch' `
        @('AppBearer') @('200', '401', '403', '404', '422')
    Assert-Operation $document '/api/v1/assets/{asset_id}/content' 'get' `
        @('AppBearer', 'AdminSession') @('200', '401', '404')
    Assert-Operation $document '/api/v1/assets/{asset_id}/content' 'delete' `
        @('AppBearer') @('200', '401', '403', '404', '409')
    Assert-Operation $document '/api/v1/assets/{asset_id}/references' 'get' `
        @('AppBearer') @('200', '401', '403', '404')

    Assert-Operation $document '/api/v1/jobs' 'get' `
        @('AppBearer') @('200', '401')
    Assert-Operation $document '/api/v1/jobs' 'post' `
        @('AppBearer') @('201', '401', '409', '422', '507') -Idempotent
    Assert-Operation $document '/api/v1/jobs/{job_id}' 'get' `
        @('AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/jobs/{job_id}/cancel' 'post' `
        @('AppBearer') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}' 'get' `
        @('AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/cancel' 'post' `
        @('AppBearer') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/retry' 'post' `
        @('AppBearer') @('201', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/requery' 'post' `
        @('AppBearer') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/finish-failed' 'post' `
        @('AppBearer') @('200', '401', '404', '409') -Idempotent

    Assert-Operation $document '/api/v1/providers' 'get' `
        @('AppBearer') @('200', '401')

    $assetKind = Assert-Schema $document 'AssetKind'
    Assert-EnumContains $assetKind 'AssetKind' @(
        'person', 'garment', 'generated_output', 'mask', 'unknown'
    )
    $jobState = Assert-Schema $document 'JobState'
    Assert-EnumContains $jobState 'JobState' @(
        'queued', 'waiting_provider', 'preparing', 'running', 'needs_attention',
        'succeeded', 'partially_succeeded', 'failed', 'cancelled', 'unknown'
    )
    $jobItemState = Assert-Schema $document 'JobItemState'
    Assert-EnumContains $jobItemState 'JobItemState' @(
        'queued', 'waiting_provider', 'preparing', 'running', 'needs_attention',
        'succeeded', 'failed', 'cancelled', 'unknown'
    )
    $blockReason = Assert-Schema $document 'JobBlockReason'
    Assert-EnumContains $blockReason 'JobBlockReason' @(
        'provider_offline', 'storage_capacity', 'retry_backoff',
        'locked_configuration_unavailable', 'external_state_unknown',
        'configuration_invalid', 'unknown'
    )
    $referenceKind = Assert-Schema $document 'AssetReferenceKind'
    Assert-EnumContains $referenceKind 'AssetReferenceKind' @(
        'job', 'job_item', 'outfit', 'generated_output', 'unknown'
    )
    $deletionOutcome = Assert-Schema $document 'AssetContentDeletionOutcome'
    Assert-EnumContains $deletionOutcome 'AssetContentDeletionOutcome' @(
        'content_deleted', 'already_deleted', 'unknown'
    )

    $asset = Assert-Schema $document 'Asset'
    Assert-SchemaProperties $asset 'Asset' @(
        'favorite', 'lifecycle', 'content_available', 'garment_category', 'garment_source'
    )
    Assert-EnumContains (Get-Property $asset.properties 'lifecycle') 'Asset.lifecycle' @(
        'active', 'deleted_content', 'expired', 'unknown'
    )
    $generatedOutput = Assert-Schema $document 'GeneratedOutput'
    Assert-SchemaProperties $generatedOutput 'GeneratedOutput' @(
        'job_item_id', 'asset_id', 'favorite', 'content_available', 'actual_parameters'
    )
    Assert-IdentifierProperty $generatedOutput 'GeneratedOutput' 'asset_id'
    $assetReference = Assert-Schema $document 'AssetReference'
    Assert-SchemaProperties $assetReference 'AssetReference' @(
        'asset_id', 'source_kind', 'source_id', 'label', 'active', 'created_at'
    )
    Assert-IdentifierProperty $assetReference 'AssetReference' 'source_id'
    Assert-IdentifierProperty $assetReference 'AssetReference' 'asset_id'

    $jobItem = Assert-Schema $document 'JobItem'
    Assert-SchemaProperties $jobItem 'JobItem' @(
        'state', 'attempt', 'retry_of_job_item_id', 'superseded_by_job_item_id',
        'external_execution_id', 'outputs', 'error', 'block_reason'
    )
    Assert-IdentifierProperty $jobItem 'JobItem' 'retry_of_job_item_id'
    Assert-IdentifierProperty $jobItem 'JobItem' 'superseded_by_job_item_id'
    $tryOnJob = Assert-Schema $document 'TryOnJob'
    Assert-SchemaProperties $tryOnJob 'TryOnJob' @(
        'mask_asset_id', 'related_job_id', 'provider_config_ref', 'provider_snapshot',
        'workflow_version_ref', 'block_reason', 'blocked_detail', 'items'
    )
    Assert-IdentifierProperty $tryOnJob 'TryOnJob' 'related_job_id'
    Assert-IdentifierProperty $tryOnJob 'TryOnJob' 'mask_asset_id'
    $createJobRequest = Assert-Schema $document 'CreateJobRequest'
    Assert-SchemaProperties $createJobRequest 'CreateJobRequest' @(
        'mask_asset_id', 'related_job_id', 'generation_options'
    )
    $retryRequest = Assert-Schema $document 'RetryJobItemRequest'
    Assert-SchemaProperties $retryRequest 'RetryJobItemRequest' @('provider_id', 'reason')

    $problemDetails = Assert-Schema $document 'ProblemDetails'
    Assert-SchemaProperties $problemDetails 'ProblemDetails' @(
        'code', 'detail', 'retryable', 'field_errors', 'context'
    )
    $problemContext = Get-Property $problemDetails.properties 'context'
    if ((Get-Property $problemContext 'additionalProperties') -ne $true) {
        throw 'ProblemDetails.context must remain extensible safe structured data.'
    }

    $bundledText = Get-Content -Raw -LiteralPath $temporaryJson
    foreach ($token in @(
        'Active references block deletion and can be inspected through the asset references resource',
        'Source identifiers are',
        'retaining',
        'reference_count'
    )) {
        if (-not $bundledText.Contains($token)) {
            throw "Bundled Phase 6 contract is missing required evidence: $token"
        }
    }
    if ($bundledText -match '/api/v1/outfits(?:/|:|")') {
        throw 'V1.1 Outfit paths must not be present in the Phase 6 contract.'
    }
    if ($bundledText -match 'relative_path') {
        throw 'Phase 6 contract must not expose storage relative paths.'
    }

    Write-Output 'Phase 6 Android V1 asset, job, lineage, content, and unknown-enum boundary verification passed.'
}
finally {
    if (Test-Path -LiteralPath $temporaryJson) {
        Remove-Item -LiteralPath $temporaryJson -Force -ErrorAction SilentlyContinue
    }
}
