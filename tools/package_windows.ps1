param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$projectToml = Get-Content -LiteralPath (Join-Path $repoRoot 'pyproject.toml') -Raw
if ($projectToml -notmatch '(?ms)^\[project\].*?^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
    throw 'A stable semantic version could not be read from pyproject.toml.'
}
$projectVersion = $Matches[1]
if ($Version -ne $projectVersion) {
    throw "Release tag version $Version does not match pyproject.toml version $projectVersion."
}
$versionModule = Get-Content -LiteralPath (Join-Path $repoRoot 'src\classicvoice\__init__.py') -Raw
if ($versionModule -notmatch '(?m)^__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$' -or $Matches[1] -ne $projectVersion) {
    throw 'The package version in pyproject.toml and src/classicvoice/__init__.py must match.'
}

$buildRoot = Join-Path $repoRoot 'dist\ClassicVoice'
if (-not (Test-Path -LiteralPath (Join-Path $buildRoot 'ClassicVoice.exe'))) {
    throw "ClassicVoice.exe is missing from the build folder: $buildRoot"
}
foreach ($requiredFile in @(
    'THIRD_PARTY.md',
    'licenses\eSpeak-NG-COPYING.txt',
    'licenses\espeak-ng-1.52.0-source.zip',
    'licenses\Kokoro-82M-Apache-2.0.txt',
    'licenses\phonemizer-GPL-3.0.txt',
    'licenses\phonemizer-3.4.0-source.tar.gz',
    'licenses\onnxruntime-ThirdPartyNotices.txt'
)) {
    $buildFile = if ($requiredFile -eq 'THIRD_PARTY.md') {
        Join-Path $buildRoot '_internal\licenses\THIRD_PARTY.md'
    }
    else {
        Join-Path $buildRoot (Join-Path '_internal' $requiredFile)
    }
    if (-not (Test-Path -LiteralPath $buildFile)) {
        throw "The application package is missing required license material: $requiredFile"
    }
}

$distRoot = Join-Path $repoRoot 'dist'
$stageRoot = Join-Path $distRoot ('.ClassicVoice-package-' + [guid]::NewGuid().ToString('N'))
$packageRoot = Join-Path $stageRoot "ClassicVoice-$Version"
$appFolder = Join-Path $packageRoot 'ClassicVoice'
$archivePath = Join-Path $distRoot "ClassicVoice-$Version-windows-x64.zip"
$checksumPath = Join-Path $distRoot "ClassicVoice-$Version-windows-x64.sha256"

try {
    New-Item -ItemType Directory -Path $appFolder -Force | Out-Null
    Copy-Item -Path (Join-Path $buildRoot '*') -Destination $appFolder -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install_windows.ps1') -Destination (Join-Path $packageRoot 'Install-ClassicVoice.ps1')
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall_windows.ps1') -Destination (Join-Path $packageRoot 'Uninstall-ClassicVoice.ps1')
    Set-Content -LiteralPath (Join-Path $packageRoot 'VERSION.txt') -Value $Version -Encoding ascii
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install-ClassicVoice.bat') -Destination $packageRoot
    Copy-Item -LiteralPath (Join-Path $repoRoot 'LICENSE') -Destination $packageRoot
    Copy-Item -LiteralPath (Join-Path $repoRoot 'THIRD_PARTY.md') -Destination $packageRoot
    @'
CLASSICVOICE — INSTALACIÓN EN WINDOWS

1. Extrae el ZIP completo.
2. Haz doble clic en Install-ClassicVoice.bat.
3. Abre ClassicVoice desde el escritorio o el menú Inicio.

No requiere Python, permisos de administrador ni conexión después de instalar.
Para probar la copia portátil, ejecuta ClassicVoice\ClassicVoice.exe.
Tus ajustes y los WAV que guardes se mantienen fuera de la carpeta de instalación.

Consulta THIRD_PARTY.md para las licencias incluidas.
'@ | Set-Content -LiteralPath (Join-Path $packageRoot 'LEEME-ANTES-DE-INSTALAR.txt') -Encoding utf8

    if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force }
    if (Test-Path -LiteralPath $checksumPath) { Remove-Item -LiteralPath $checksumPath -Force }
    Compress-Archive -Path $packageRoot -DestinationPath $archivePath -CompressionLevel Optimal
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        $entries = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($entry in $archive.Entries) { [void]$entries.Add($entry.FullName) }
        foreach ($requiredEntry in @(
            "ClassicVoice-$Version/ClassicVoice/ClassicVoice.exe",
            "ClassicVoice-$Version/ClassicVoice/_internal/licenses/eSpeak-NG-COPYING.txt",
            "ClassicVoice-$Version/ClassicVoice/_internal/licenses/espeak-ng-1.52.0-source.zip",
            "ClassicVoice-$Version/ClassicVoice/_internal/licenses/Kokoro-82M-Apache-2.0.txt",
            "ClassicVoice-$Version/ClassicVoice/_internal/licenses/phonemizer-GPL-3.0.txt",
            "ClassicVoice-$Version/ClassicVoice/_internal/licenses/phonemizer-3.4.0-source.tar.gz",
            "ClassicVoice-$Version/ClassicVoice/_internal/licenses/onnxruntime-ThirdPartyNotices.txt",
            "ClassicVoice-$Version/Install-ClassicVoice.bat",
            "ClassicVoice-$Version/Install-ClassicVoice.ps1",
            "ClassicVoice-$Version/Uninstall-ClassicVoice.ps1"
        )) {
            if (-not $entries.Contains($requiredEntry)) {
                throw "The release ZIP is incomplete: $requiredEntry was not found."
            }
        }
    }
    finally {
        $archive.Dispose()
    }
    $hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $checksumPath -Value "$hash *$(Split-Path -Leaf $archivePath)" -Encoding ascii
    Write-Host "Windows package: $archivePath"
    Write-Host "SHA-256 file: $checksumPath"
}
finally {
    if (Test-Path -LiteralPath $stageRoot) {
        $resolvedDist = [IO.Path]::GetFullPath($distRoot).TrimEnd('\')
        $resolvedStage = [IO.Path]::GetFullPath($stageRoot).TrimEnd('\')
        $expectedPrefix = $resolvedDist + '\.ClassicVoice-package-'
        if (-not $resolvedStage.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean a package staging path outside the expected folder: $resolvedStage"
        }
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
