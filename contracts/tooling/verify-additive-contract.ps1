[CmdletBinding()]
param(
    [string]$Baseline,
    [string]$Current
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$baselinePath = if ([string]::IsNullOrWhiteSpace($Baseline)) {
    Join-Path $repositoryRoot 'contracts\openapi\baselines\phase-1-openapi.yaml'
}
else {
    (Resolve-Path -LiteralPath $Baseline).Path
}
$currentPath = if ([string]::IsNullOrWhiteSpace($Current)) {
    Join-Path $repositoryRoot 'contracts\generated\openapi.yaml'
}
else {
    (Resolve-Path -LiteralPath $Current).Path
}
$toolExtension = if ($env:OS -eq 'Windows_NT') { '.cmd' } else { '' }
$redocly = Join-Path $PSScriptRoot ('node_modules\.bin\redocly' + $toolExtension)

if (-not (Test-Path -LiteralPath $redocly)) {
    throw 'Missing Redocly CLI. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
}

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-openapi-additive-' + [System.Guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null

function Convert-BundleToDocument([string]$Source, [string]$Name) {
    $output = Join-Path $temporaryRoot ($Name + '.json')
    & $redocly 'bundle' $Source '--output' $output '--ext' 'json'
    if ($LASTEXITCODE -ne 0) {
        throw "Could not bundle $Name contract as JSON."
    }
    return Get-Content -Raw -LiteralPath $output | ConvertFrom-Json -Depth 100
}

function Get-Property($Object, [string]$Name) {
    if ($null -eq $Object) {
        return $null
    }
    return $Object.PSObject.Properties[$Name].Value
}

function Assert-PropertyPresent($Object, [string]$Name, [string]$Context) {
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name]) {
        throw "Breaking contract change: missing $Context '$Name'."
    }
}

function Get-SortedStrings($Values) {
    if ($null -eq $Values) {
        return @()
    }
    return @($Values | ForEach-Object { [string]$_ } | Sort-Object -Unique)
}

try {
    $baselineDocument = Convert-BundleToDocument $baselinePath 'baseline'
    $currentDocument = Convert-BundleToDocument $currentPath 'current'
    $methods = @('get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace')

    foreach ($baselinePathProperty in $baselineDocument.paths.PSObject.Properties) {
        $pathName = $baselinePathProperty.Name
        Assert-PropertyPresent $currentDocument.paths $pathName 'path'
        $currentPathItem = Get-Property $currentDocument.paths $pathName

        foreach ($method in $methods) {
            $baselineOperationProperty = $baselinePathProperty.Value.PSObject.Properties[$method]
            if ($null -eq $baselineOperationProperty) {
                continue
            }
            Assert-PropertyPresent $currentPathItem $method "operation on $pathName"
            $baselineOperation = $baselineOperationProperty.Value
            $currentOperation = Get-Property $currentPathItem $method

            if ($baselineOperation.operationId -ne $currentOperation.operationId) {
                throw "Breaking contract change: operationId changed for $method $pathName."
            }

            $baselineSecurity = $baselineOperation.security | ConvertTo-Json -Depth 20 -Compress
            $currentSecurity = $currentOperation.security | ConvertTo-Json -Depth 20 -Compress
            if ($baselineSecurity -ne $currentSecurity) {
                throw "Breaking contract change: security changed for $method $pathName."
            }

            foreach ($responseProperty in $baselineOperation.responses.PSObject.Properties) {
                Assert-PropertyPresent $currentOperation.responses $responseProperty.Name `
                    "response on $method $pathName"
            }
        }
    }

    foreach ($baselineScheme in $baselineDocument.components.securitySchemes.PSObject.Properties) {
        Assert-PropertyPresent $currentDocument.components.securitySchemes $baselineScheme.Name `
            'security scheme'
        $currentScheme = Get-Property $currentDocument.components.securitySchemes $baselineScheme.Name
        foreach ($field in @('type', 'in', 'name', 'scheme')) {
            $baselineValue = Get-Property $baselineScheme.Value $field
            if ($null -ne $baselineValue -and $baselineValue -ne (Get-Property $currentScheme $field)) {
                throw "Breaking contract change: security scheme '$($baselineScheme.Name)' changed '$field'."
            }
        }
    }

    foreach ($baselineSchemaProperty in $baselineDocument.components.schemas.PSObject.Properties) {
        $schemaName = $baselineSchemaProperty.Name
        Assert-PropertyPresent $currentDocument.components.schemas $schemaName 'schema'
        $baselineSchema = $baselineSchemaProperty.Value
        $currentSchema = Get-Property $currentDocument.components.schemas $schemaName

        if ($null -ne $baselineSchema.properties) {
            foreach ($property in $baselineSchema.properties.PSObject.Properties) {
                Assert-PropertyPresent $currentSchema.properties $property.Name `
                    "property on schema $schemaName"
            }
        }

        $baselineRequired = Get-SortedStrings $baselineSchema.required
        $currentRequired = Get-SortedStrings $currentSchema.required
        if (($baselineRequired -join "`n") -ne ($currentRequired -join "`n")) {
            throw "Breaking contract change: required properties changed on schema '$schemaName'."
        }

        $baselineEnum = Get-SortedStrings $baselineSchema.enum
        $currentEnum = Get-SortedStrings $currentSchema.enum
        foreach ($value in $baselineEnum) {
            if ($value -notin $currentEnum) {
                throw "Breaking contract change: enum value '$value' was removed from '$schemaName'."
            }
        }
    }

    Write-Output 'Additive compatibility check passed against the Phase 1 contract surface.'
}
finally {
    $temporaryFullPath = [System.IO.Path]::GetFullPath($temporaryRoot)
    $systemTempPrefix = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (
        $temporaryFullPath.StartsWith($systemTempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $temporaryFullPath -Leaf).StartsWith('clothes-model-openapi-additive-')
    ) {
        Remove-Item -LiteralPath $temporaryFullPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}
