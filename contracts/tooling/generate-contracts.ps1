[CmdletBinding()]
param(
    [string]$OutputRoot
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$resolvedOutputRoot = if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $repositoryRoot
}
else {
    [System.IO.Path]::GetFullPath($OutputRoot)
}
$source = Join-Path $repositoryRoot 'contracts\openapi\openapi.yaml'
$redoclyConfig = Join-Path $PSScriptRoot 'redocly.yaml'
$backendProject = Join-Path $repositoryRoot 'backend'
$bundle = Join-Path $resolvedOutputRoot 'contracts\generated\openapi.yaml'
$backendGenerated = Join-Path $resolvedOutputRoot 'backend\src\clothes_model\generated'
$androidGenerated = Join-Path $resolvedOutputRoot 'android\core\api-contract'
$androidGeneratedSource = Join-Path $androidGenerated 'src\main\kotlin'
$webGenerated = Join-Path $resolvedOutputRoot 'web-admin\src\api\generated'
$nodeToolBin = Join-Path $PSScriptRoot 'node_modules\.bin'
$runningOnWindows = $env:OS -eq 'Windows_NT'
$uvCommand = if ($env:CLOTHES_MODEL_UV) {
    $env:CLOTHES_MODEL_UV
}
else {
    $resolvedUv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $resolvedUv) { $resolvedUv.Source } else { $null }
}

function Assert-ChildPath([string]$Path) {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $prefix = $resolvedOutputRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Generated target escapes output root: $fullPath"
    }
}

function Reset-GeneratedDirectory([string]$Path) {
    Assert-ChildPath $Path
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Get-RelativeChildPath([string]$BasePath, [string]$ChildPath) {
    $base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\', '/') + `
        [System.IO.Path]::DirectorySeparatorChar
    $child = [System.IO.Path]::GetFullPath($ChildPath)
    if (-not $child.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is not a child of its generation root: $child"
    }
    return $child.Substring($base.Length)
}

function Invoke-ContractTool([string]$Name, [string[]]$Arguments) {
    $extension = if ($runningOnWindows) { '.cmd' } else { '' }
    $command = Join-Path $nodeToolBin ($Name + $extension)
    if (-not (Test-Path -LiteralPath $command)) {
        throw "Missing contract tool '$Name'. Run corepack pnpm install --frozen-lockfile in contracts/tooling."
    }
    Push-Location $PSScriptRoot
    try {
        & $command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Contract tool '$Name' failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-BackendTool([string]$Name, [string[]]$Arguments) {
    if ($null -ne $uvCommand) {
        & $uvCommand 'run' '--project' $backendProject $Name @Arguments
    }
    else {
        $extension = if ($runningOnWindows) { '.exe' } else { '' }
        $command = Join-Path $backendProject ('.venv\Scripts\' + $Name + $extension)
        if (-not (Test-Path -LiteralPath $command)) {
            throw "Missing Backend tool '$Name'. Install the locked Backend environment or set CLOTHES_MODEL_UV."
        }
        & $command @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Backend tool '$Name' failed with exit code $LASTEXITCODE."
    }
}

function Normalize-KotlinGeneratorOutput([string]$ProjectRoot) {
    # OpenAPI Generator 7.25.0 emits the same ApiKeyAuth import once per apiKey
    # security scheme. Kotlin rejects duplicate imports, so normalize that known
    # generator defect before publishing or compiling the generated client.
    $apiClient = Join-Path $ProjectRoot (
        'src\main\kotlin\com\clothesmodel\contract\infrastructure\ApiClient.kt'
    )
    $content = [System.IO.File]::ReadAllText($apiClient)
    $duplicate = "import com.clothesmodel.contract.auth.ApiKeyAuth`r?`n" +
        "import com.clothesmodel.contract.auth.ApiKeyAuth"
    $normalized = [System.Text.RegularExpressions.Regex]::Replace(
        $content,
        $duplicate,
        'import com.clothesmodel.contract.auth.ApiKeyAuth'
    )
    [System.IO.File]::WriteAllText(
        $apiClient,
        $normalized,
        [System.Text.UTF8Encoding]::new($false)
    )

    # Free-form JSON objects are emitted as Map<String, Any>. kotlinx.serialization
    # cannot create a serializer for Any, while JsonElement preserves the same
    # JSON boundary without inventing a narrower product contract.
    $models = Join-Path $ProjectRoot 'src\main\kotlin\com\clothesmodel\contract\model'
    foreach ($model in Get-ChildItem -LiteralPath $models -File -Filter '*.kt') {
        $modelContent = [System.IO.File]::ReadAllText($model.FullName)
        $modelNormalized = $modelContent.Replace(
            'kotlin.collections.Map<kotlin.String, kotlin.Any>',
            'kotlin.collections.Map<kotlin.String, kotlinx.serialization.json.JsonElement>'
        )
        if ($modelNormalized -ne $modelContent) {
            [System.IO.File]::WriteAllText(
                $model.FullName,
                $modelNormalized,
                [System.Text.UTF8Encoding]::new($false)
            )
        }
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path $bundle) | Out-Null
Invoke-ContractTool 'redocly' @('lint', $source, '--config', $redoclyConfig)
Invoke-ContractTool 'redocly' @(
    'bundle', $source,
    '--config', $redoclyConfig,
    '--output', $bundle
)

Reset-GeneratedDirectory $backendGenerated
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'templates\backend-generated-init.py') `
    -Destination (Join-Path $backendGenerated '__init__.py')
Invoke-BackendTool 'datamodel-codegen' @(
    '--input', $bundle,
    '--input-file-type', 'openapi',
    '--output', (Join-Path $backendGenerated 'models.py'),
    '--output-model-type', 'pydantic_v2.BaseModel',
    '--target-python-version', '3.14',
    '--use-standard-collections',
    '--use-union-operator',
    '--use-schema-description',
    '--field-constraints',
    '--disable-timestamp'
)

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-codegen-' + [System.Guid]::NewGuid().ToString('N')
)
$kotlinProject = Join-Path $temporaryRoot 'kotlin'
$webProject = Join-Path $temporaryRoot 'web'
New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null

try {
    Invoke-ContractTool 'openapi-generator-cli' @(
        'generate',
        '-i', $bundle,
        '-g', 'kotlin',
        '-o', $kotlinProject,
        '--package-name', 'com.clothesmodel.contract',
        '--api-package', 'com.clothesmodel.contract.api',
        '--model-package', 'com.clothesmodel.contract.model',
        '--additional-properties',
        'library=jvm-retrofit2,serializationLibrary=kotlinx_serialization,useCoroutines=true,enumUnknownDefaultCase=true,dateLibrary=java8,useSettingsGradle=true,artifactId=api-contract',
        '--global-property', 'apiDocs=false,modelDocs=false,apiTests=false,modelTests=false'
    )
    Normalize-KotlinGeneratorOutput $kotlinProject

    Reset-GeneratedDirectory $androidGeneratedSource
    $androidSource = Join-Path $kotlinProject 'src\main\kotlin'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'templates\android-generated-readme.md') `
        -Destination (Join-Path $androidGenerated 'README.md')
    foreach ($sourceChild in Get-ChildItem -LiteralPath $androidSource) {
        Copy-Item -LiteralPath $sourceChild.FullName `
            -Destination $androidGeneratedSource `
            -Recurse
    }

    Invoke-ContractTool 'openapi-generator-cli' @(
        'generate',
        '-i', $bundle,
        '-g', 'typescript-fetch',
        '-o', $webProject,
        '--additional-properties',
        'supportsES6=true,useSingleRequestParameter=true,withInterfaces=true,enumUnknownDefaultCase=true',
        '--global-property', 'apiDocs=false,modelDocs=false,apiTests=false,modelTests=false'
    )

    Reset-GeneratedDirectory $webGenerated
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'templates\web-generated-readme.md') `
        -Destination (Join-Path $webGenerated 'README.md')
    foreach ($file in Get-ChildItem -LiteralPath $webProject -Recurse -File -Filter '*.ts') {
        $relative = Get-RelativeChildPath $webProject $file.FullName
        $destination = Join-Path $webGenerated $relative
        New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination
    }
}
finally {
    $temporaryFullPath = [System.IO.Path]::GetFullPath($temporaryRoot)
    $systemTempPrefix = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (
        $temporaryFullPath.StartsWith($systemTempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $temporaryFullPath -Leaf).StartsWith('clothes-model-codegen-')
    ) {
        Remove-Item -LiteralPath $temporaryFullPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Output "Generated contract artifacts under $resolvedOutputRoot"
