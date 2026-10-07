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
    'clothes-model-phase5-contract-' + [System.Guid]::NewGuid().ToString('N') + '.json'
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
        throw "Missing Phase 5 contract operation: $($Method.ToUpperInvariant()) $Path"
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
        throw "Missing Phase 5 shared schema: $Name"
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
            throw "Enum '$Name' is missing Phase 5 value '$value'."
        }
    }
}

try {
    if (-not (Test-Path -LiteralPath $redocly)) {
        throw 'Missing Redocly CLI. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
    }
    & $redocly 'bundle' $currentPath '--output' $temporaryJson '--ext' 'json'
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not bundle the Phase 5 contract for boundary verification.'
    }
    $document = Get-Content -Raw -LiteralPath $temporaryJson | ConvertFrom-Json -Depth 100

    Assert-Operation $document '/api/v1/admin/workflows' 'get' `
        @('AdminSession') @('200', '401')
    Assert-Operation $document '/api/v1/admin/workflows' 'post' `
        @('AdminCsrf+AdminSession') @('201', '401', '409', '422', '507') -Idempotent
    Assert-Operation $document '/api/v1/admin/workflows/{workflow_version_id}' 'get' `
        @('AdminSession') @('200', '401', '404')
    Assert-Operation $document '/api/v1/admin/workflows/{workflow_version_id}/validate' 'post' `
        @('AdminCsrf+AdminSession') @('200', '401', '404', '409', '422', '507') -Idempotent
    Assert-Operation $document '/api/v1/admin/workflows/{workflow_version_id}/activate' 'post' `
        @('AdminCsrf+AdminSession') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/admin/workflows/{workflow_version_id}/retire' 'post' `
        @('AdminCsrf+AdminSession') @('200', '401', '404', '409') -Idempotent
    Assert-Operation $document '/api/v1/admin/configuration/comfy-node' 'get' `
        @('AdminSession') @('200', '401')
    Assert-Operation $document '/api/v1/admin/configuration/comfy-node' 'put' `
        @('AdminCsrf+AdminSession') @('200', '401')
    Assert-Operation $document '/api/v1/admin/configuration/comfy-node/test' 'post' `
        @('AdminCsrf+AdminSession') @('200', '401') -Idempotent

    $workflowState = Assert-Schema $document 'WorkflowState'
    Assert-EnumContains $workflowState 'WorkflowState' @(
        'draft', 'validated', 'active', 'retired', 'unknown'
    )
    $compatibilityState = Assert-Schema $document 'WorkflowCompatibilityState'
    Assert-EnumContains $compatibilityState 'WorkflowCompatibilityState' @(
        'compatible', 'incompatible', 'offline', 'unchecked', 'unknown'
    )

    $workflowVersion = Assert-Schema $document 'WorkflowVersion'
    Assert-SchemaProperties $workflowVersion 'WorkflowVersion' @(
        'logical_provider_ref', 'artifacts', 'manifest_summary', 'validation_status',
        'validated_at', 'activated_at', 'retired_at', 'compatibility'
    )
    $artifactMetadata = Assert-Schema $document 'WorkflowArtifactMetadata'
    Assert-SchemaProperties $artifactMetadata 'WorkflowArtifactMetadata' @(
        'workflow_sha256', 'manifest_sha256', 'workflow_size_bytes', 'manifest_size_bytes'
    )
    $manifestSummary = Assert-Schema $document 'WorkflowManifestSummary'
    Assert-SchemaProperties $manifestSummary 'WorkflowManifestSummary' @(
        'schema_version', 'binding_keys', 'output_count', 'capabilities'
    )
    Assert-Schema $document 'WorkflowValidationCheck' | Out-Null
    Assert-Schema $document 'WorkflowCompatibilityResult' | Out-Null
    Assert-Schema $document 'WorkflowRetireRequest' | Out-Null

    $workflowRef = Assert-Schema $document 'WorkflowVersionRef'
    Assert-SchemaProperties $workflowRef 'WorkflowVersionRef' @(
        'workflow_id', 'workflow_version_id', 'version', 'workflow_sha256', 'manifest_sha256'
    )
    $versionSnapshot = Assert-Schema $document 'VersionSnapshot'
    Assert-SchemaProperties $versionSnapshot 'VersionSnapshot' @(
        'label', 'artifact_sha256', 'manifest_sha256', 'bindings_schema_version'
    )

    $nodeConfigRequest = Assert-Schema $document 'ComfyNodeConfigurationRequest'
    if (-not (Get-Property $nodeConfigRequest.properties.credential 'writeOnly')) {
        throw 'Comfy node credential must remain write-only.'
    }
    $nodeConfig = Assert-Schema $document 'ComfyNodeConfiguration'
    Assert-SchemaProperties $nodeConfig 'ComfyNodeConfiguration' @(
        'logical_provider_id', 'credential_configured', 'health', 'health_detail',
        'observed_server_version', 'active_workflow_compatibility'
    )
    foreach ($forbidden in @('credential', 'secret', 'authorization')) {
        if ($null -ne $nodeConfig.properties.PSObject.Properties[$forbidden]) {
            throw "Redacted ComfyNodeConfiguration must not expose '$forbidden'."
        }
    }

    $tryOnJob = Assert-Schema $document 'TryOnJob'
    Assert-SchemaProperties $tryOnJob 'TryOnJob' @(
        'provider_config_ref', 'provider_snapshot', 'workflow_version_ref',
        'workflow_snapshot', 'block_reason', 'blocked_detail', 'next_attempt_at'
    )
    $jobState = Assert-Schema $document 'JobState'
    Assert-EnumContains $jobState 'JobState' @(
        'queued', 'waiting_provider', 'needs_attention', 'cancelled'
    )
    $blockReason = Assert-Schema $document 'JobBlockReason'
    Assert-EnumContains $blockReason 'JobBlockReason' @(
        'provider_offline', 'storage_capacity', 'locked_configuration_unavailable',
        'external_state_unknown', 'configuration_invalid'
    )

    $bundledText = Get-Content -Raw -LiteralPath $temporaryJson
    foreach ($token in @(
        'Immutable draft with canonical artifact identities',
        'Active immutable Workflow used only by newly created jobs',
        'Retired immutable version retained for history and explicit rollback',
        'Reachable replacement node lacks requirements of the locked Workflow',
        'Physical node is offline; draft remains unchanged',
        'Structural validation fails without sending inputs',
        'Persisted job stays queued with a storage-capacity block',
        'Original external execution is uncertain'
    )) {
        if (-not $bundledText.Contains($token)) {
            throw "Bundled Phase 5 contract is missing required example evidence: $token"
        }
    }

    if ($bundledText -match '"credential"\s*:\s*"[^"<]') {
        throw 'Bundled Phase 5 examples must not contain a Comfy credential value.'
    }

    Write-Output 'Phase 5 Comfy node, immutable Workflow, locking, and recovery boundary verification passed.'
}
finally {
    if (Test-Path -LiteralPath $temporaryJson) {
        Remove-Item -LiteralPath $temporaryJson -Force -ErrorAction SilentlyContinue
    }
}
