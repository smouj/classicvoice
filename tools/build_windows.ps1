param(
    [switch]$Install
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$workRoot = $null
Push-Location $repoRoot

try {
    $projectToml = Get-Content -LiteralPath (Join-Path $repoRoot 'pyproject.toml') -Raw
    if ($projectToml -notmatch '(?ms)^\[project\].*?^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
        throw 'A stable semantic version could not be read from pyproject.toml.'
    }
    $appVersion = $Matches[1]
    $versionModule = Get-Content -LiteralPath (Join-Path $repoRoot 'src\classicvoice\__init__.py') -Raw
    if ($versionModule -notmatch '(?m)^__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$' -or $Matches[1] -ne $appVersion) {
        throw 'The package version in pyproject.toml and src/classicvoice/__init__.py must match.'
    }

    $engineRoot = Join-Path $repoRoot 'bin\espeak-ng'
    $engineExe = Join-Path $engineRoot 'espeak-ng.exe'
    $engineData = Join-Path $engineRoot 'espeak-ng-data'

    if (-not (Test-Path -LiteralPath $engineExe)) {
        if (Test-Path -LiteralPath $engineRoot) {
            throw "The engine folder exists but is incomplete: $engineRoot"
        }
        $workRoot = Join-Path $env:TEMP ('ClassicVoice-build-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $workRoot | Out-Null
        $msiPath = Join-Path $workRoot 'espeak-ng-1.52.0.msi'
        $extractRoot = Join-Path $workRoot 'extract'
        New-Item -ItemType Directory -Path $extractRoot | Out-Null
        Invoke-WebRequest -Uri 'https://github.com/espeak-ng/espeak-ng/releases/download/1.52.0/espeak-ng.msi' -OutFile $msiPath

        $expectedHash = '7F673C709EA5DD579D3B5EBB98688CC575328A6AB7438D2BC405B88CEDAEAFB9'
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $msiPath).Hash
        if ($actualHash -ne $expectedHash) {
            throw "eSpeak NG checksum mismatch. Expected $expectedHash; received $actualHash."
        }

        $logPath = Join-Path $workRoot 'extract.log'
        $msiexec = Join-Path $env:SystemRoot 'System32\msiexec.exe'
        & $msiexec /a $msiPath /qn /norestart "TARGETDIR=$extractRoot" /l*v $logPath
        if ($LASTEXITCODE -ne 0) {
            throw "eSpeak NG could not be extracted. MSI returned $LASTEXITCODE. Log: $logPath"
        }
        $engineSource = Join-Path $extractRoot 'eSpeak NG'
        if (-not (Test-Path -LiteralPath (Join-Path $engineSource 'espeak-ng.exe')) -or
            -not (Test-Path -LiteralPath (Join-Path $engineSource 'espeak-ng-data'))) {
            throw "The verified eSpeak NG package did not contain the expected files. Log: $logPath"
        }
        New-Item -ItemType Directory -Path $engineRoot | Out-Null
        Copy-Item -Path (Join-Path $engineSource '*') -Destination $engineRoot -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $engineData)) {
        throw "The eSpeak NG voice data is missing: $engineData"
    }

    $sourceArchive = Join-Path $repoRoot 'licenses\espeak-ng-1.52.0-source.zip'
    if (-not (Test-Path -LiteralPath $sourceArchive)) {
        Invoke-WebRequest -Uri 'https://github.com/espeak-ng/espeak-ng/archive/refs/tags/1.52.0.zip' -OutFile $sourceArchive
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($sourceArchive)
    try {
        if ($archive.Entries.Count -lt 100 -or
            -not ($archive.Entries | Where-Object FullName -match '1\.52\.0/.+COPYING$')) {
            throw 'The eSpeak NG source archive does not match the expected release.'
        }
    }
    finally {
        $archive.Dispose()
    }

    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'assets\classicvoice.ico'))) {
        throw 'The app icon is missing: assets\classicvoice.ico'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'licenses\eSpeak-NG-COPYING.txt'))) {
        throw 'The eSpeak NG license notice is missing.'
    }

    $python = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & py -3.11 -m venv (Join-Path $repoRoot '.venv')
        if ($LASTEXITCODE -ne 0) {
            throw 'Python 3.11 is required to create the build environment.'
        }
    }
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'The local Python build environment was not created.'
    }

    & $python -m pip install --disable-pip-version-check '-e' '.[build,test]'
    if ($LASTEXITCODE -ne 0) {
        throw 'Build dependencies could not be installed.'
    }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw 'ClassicVoice checks failed. The Windows build was stopped.'
    }
    & $python (Join-Path $PSScriptRoot 'smoke_ui.py')
    if ($LASTEXITCODE -ne 0) {
        throw 'The ClassicVoice window could not be opened.'
    }

    $engineDirArgument = "$engineRoot;bin\espeak-ng"
    $assetsArgument = "$(Join-Path $repoRoot 'assets');assets"
    $licenseArgument = "$(Join-Path $repoRoot 'licenses\eSpeak-NG-COPYING.txt');licenses"
    $sourceArgument = "$(Join-Path $repoRoot 'licenses\espeak-ng-1.52.0-source.zip');licenses"
    $readmeLicenseArgument = "$(Join-Path $repoRoot 'THIRD_PARTY.md');licenses"
    $mitLicenseArgument = "$(Join-Path $repoRoot 'LICENSE');licenses"
    $iconArgument = Join-Path $repoRoot 'assets\classicvoice.ico'
    $entryPoint = Join-Path $repoRoot 'src\classicvoice\launcher.py'
    $pyinstallerArgs = @(
        '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onedir',
        '--name', 'ClassicVoice',
        '--icon', $iconArgument,
        '--paths', (Join-Path $repoRoot 'src'),
        '--add-data', $engineDirArgument,
        '--add-data', $assetsArgument,
        '--add-data', $licenseArgument,
        '--add-data', $sourceArgument,
        '--add-data', $readmeLicenseArgument,
        '--add-data', $mitLicenseArgument,
        '--distpath', (Join-Path $repoRoot 'dist'),
        '--workpath', (Join-Path $repoRoot 'build'),
        $entryPoint
    )
    & $python @pyinstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller could not create the Windows desktop app.'
    }

    $builtApp = Join-Path $repoRoot 'dist\ClassicVoice\ClassicVoice.exe'
    if (-not (Test-Path -LiteralPath $builtApp)) {
        throw 'The Windows desktop app was not created.'
    }

    if ($Install) {
        & (Join-Path $PSScriptRoot 'install_windows.ps1') -BuildPath (Join-Path $repoRoot 'dist\ClassicVoice') -Version $appVersion
        if ($LASTEXITCODE -ne 0) {
            throw 'The app was built, but its per-user installation did not finish.'
        }
        & $python (Join-Path $PSScriptRoot 'smoke_installed.py') --install-dir (Join-Path $env:LOCALAPPDATA 'Programs\ClassicVoice')
        if ($LASTEXITCODE -ne 0) {
            throw 'The installed engine could not complete its WAV export smoke check.'
        }
    }

    Write-Host "ClassicVoice $appVersion built at $builtApp"
}
finally {
    try {
        if ($workRoot -and (Test-Path -LiteralPath $workRoot)) {
            $resolvedTemp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
            $resolvedWork = [IO.Path]::GetFullPath($workRoot).TrimEnd('\')
            if (-not $resolvedWork.StartsWith(($resolvedTemp + '\ClassicVoice-build-'), [StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to clean a build work folder outside the expected temporary location: $resolvedWork"
            }
            Remove-Item -LiteralPath $resolvedWork -Recurse -Force
        }
    }
    finally {
        Pop-Location
    }
}
