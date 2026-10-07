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
    'clothes-model-phase3-contract-' + [System.Guid]::NewGuid().ToString('N') + '.json'
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
        throw "Missing Phase 3 contract operation: $($Method.ToUpperInvariant()) $Path"
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
        throw "Missing Phase 3 shared schema: $Name"
    }
    return (Get-Property $Document.components.schemas $Name)
}

function Assert-EnumValues($Schema, [string]$Name, [string[]]$Expected) {
    $actual = @($Schema.enum | ForEach-Object { [string]$_ } | Sort-Object -Unique)
    $wanted = @($Expected | Sort-Object -Unique)
    if (($actual -join ',') -ne ($wanted -join ',')) {
        throw "Unexpected enum for $Name. Expected=$($wanted -join ',') Actual=$($actual -join ',')"
    }
}

function Assert-SchemaProperties($Schema, [string]$Name, [string[]]$Expected) {
    foreach ($property in $Expected) {
        if ($null -eq $Schema.properties.PSObject.Properties[$property]) {
            throw "Missing property '$property' on schema '$Name'."
        }
    }
}

try {
    if (-not (Test-Path -LiteralPath $redocly)) {
        throw 'Missing Redocly CLI. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
    }
    & $redocly 'bundle' $currentPath '--output' $temporaryJson '--ext' 'json'
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not bundle the Phase 3 contract for boundary verification.'
    }
    $document = Get-Content -Raw -LiteralPath $temporaryJson | ConvertFrom-Json -Depth 100

    $jobState = Assert-Schema $document 'JobState'
    Assert-EnumValues $jobState 'JobState' @(
        'queued', 'waiting_provider', 'preparing', 'running', 'needs_attention',
        'succeeded', 'partially_succeeded', 'failed', 'cancelled', 'unknown'
    )
    $jobItemState = Assert-Schema $document 'JobItemState'
    Assert-EnumValues $jobItemState 'JobItemState' @(
        'queued', 'waiting_provider', 'preparing', 'running', 'needs_attention',
        'succeeded', 'failed', 'cancelled', 'unknown'
    )
    if (@($jobItemState.enum) -contains 'partially_succeeded') {
        throw 'JobItemState must not contain the aggregate-only partially_succeeded state.'
    }

    $blockReason = Assert-Schema $document 'JobBlockReason'
    Assert-EnumValues $blockReason 'JobBlockReason' @(
        'provider_offline', 'storage_capacity', 'retry_backoff',
        'locked_configuration_unavailable', 'external_state_unknown',
        'configuration_invalid', 'unknown'
    )
    $availability = Assert-Schema $document 'ProviderAvailability'
    Assert-EnumValues $availability 'ProviderAvailability' @(
        'available', 'temporarily_offline', 'unavailable_configuration', 'disabled', 'unknown'
    )

    $providerSnapshot = Assert-Schema $document 'ProviderSnapshot'
    Assert-SchemaProperties $providerSnapshot 'ProviderSnapshot' @(
        'label', 'adapter_type', 'model', 'semantic_parameters',
        'capabilities_schema_version', 'capabilities'
    )
    Assert-Schema $document 'ProviderCapabilities' | Out-Null

    $jobItem = Assert-Schema $document 'JobItem'
    Assert-SchemaProperties $jobItem 'JobItem' @(
        'attempt', 'retry_of_job_item_id', 'superseded_by_job_item_id',
        'external_execution_id', 'next_attempt_at', 'block_reason', 'error'
    )
    $tryOnJob = Assert-Schema $document 'TryOnJob'
    Assert-SchemaProperties $tryOnJob 'TryOnJob' @(
        'provider_config_ref', 'provider_snapshot', 'workflow_version_ref',
        'block_reason', 'blocked_detail', 'next_attempt_at'
    )
    Assert-Schema $document 'JobCommandResult' | Out-Null

    Assert-Operation $document '/api/v1/jobs' 'get' @('AppBearer') @('200', '401')
    Assert-Operation $document '/api/v1/jobs' 'post' @('AppBearer') @('201', '401', '409', '422', '507') -Idempotent
    Assert-Operation $document '/api/v1/jobs/{job_id}' 'get' @('AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/jobs/{job_id}/cancel' 'post' @('AppBearer') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}' 'get' @('AppBearer') @('200', '401', '404')
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/cancel' 'post' @('AppBearer') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/retry' 'post' @('AppBearer') @('201', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/requery' 'post' @('AppBearer') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/job-items/{job_item_id}/finish-failed' 'post' @('AppBearer') @('200', '401', '404', '409') -Idempotent

    Assert-Operation $document '/api/v1/providers' 'get' @('AppBearer') @('200', '401')
    Assert-Operation $document '/api/v1/admin/provider-configs' 'get' @('AdminSession') @('200', '401')
    Assert-Operation $document '/api/v1/admin/provider-configs' 'post' @('AdminCsrf+AdminSession') @('201', '401', '409') -Idempotent
    Assert-Operation $document '/api/v1/admin/provider-configs/{provider_id}' 'get' @('AdminSession') @('200', '401', '404')
    Assert-Operation $document '/api/v1/admin/provider-configs/{provider_id}' 'patch' @('AdminCsrf+AdminSession') @('200', '401', '404')
    Assert-Operation $document '/api/v1/admin/provider-configs/{provider_id}/validate' 'post' @('AdminCsrf+AdminSession') @('200', '401', '404') -Idempotent
    Assert-Operation $document '/api/v1/admin/provider-configs/{provider_id}/enable' 'post' @('AdminCsrf+AdminSession') @('200', '401', '404', '409') -Idempotent

    $providerConfigRequest = Assert-Schema $document 'ProviderConfigRequest'
    if ($null -eq $providerConfigRequest.properties.PSObject.Properties['api_key']) {
        throw "ProviderConfigRequest must declare the write-only api_key input."
    }
    $providerConfig = Assert-Schema $document 'ProviderConfig'
    foreach ($forbidden in @('api_key', 'secret', 'vendor_parameters')) {
        if ($null -ne $providerConfig.properties.PSObject.Properties[$forbidden]) {
            throw "Redacted ProviderConfig must not expose '$forbidden'."
        }
    }
    foreach ($required in @('secret_configured', 'config_ref')) {
        if ($null -eq $providerConfig.properties.PSObject.Properties[$required]) {
            throw "ProviderConfig must expose redaction field '$required'."
        }
    }

    $bundledText = Get-Content -Raw -LiteralPath $temporaryJson

    Write-Output 'Phase 3 job, provider, idempotency, and redaction boundary verification passed.'
}
finally {
    if (Test-Path -LiteralPath $temporaryJson) {
        Remove-Item -LiteralPath $temporaryJson -Force -ErrorAction SilentlyContinue
    }
}
