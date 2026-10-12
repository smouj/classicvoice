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
        $downloadSucceeded = $false
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                Invoke-WebRequest `
                    -Uri 'https://github.com/espeak-ng/espeak-ng/releases/download/1.52.0/espeak-ng.msi' `
                    -OutFile $msiPath `
                    -TimeoutSec 90
                $downloadSucceeded = $true
                break
            }
            catch {
                if (Test-Path -LiteralPath $msiPath) {
                    Remove-Item -LiteralPath $msiPath -Force
                }
                if ($attempt -eq 3) {
                    throw "eSpeak NG download failed after $attempt attempts: $($_.Exception.Message)"
                }
                Start-Sleep -Seconds (5 * $attempt)
            }
        }
        if (-not $downloadSucceeded) {
            throw 'The verified eSpeak NG MSI could not be downloaded.'
        }

        $expectedHash = '7F673C709EA5DD579D3B5EBB98688CC575328A6AB7438D2BC405B88CEDAEAFB9'
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $msiPath).Hash
        if ($actualHash -ne $expectedHash) {
            throw "eSpeak NG checksum mismatch. Expected $expectedHash; received $actualHash."
        }

        $logPath = Join-Path $workRoot 'extract.log'
        $msiexec = Join-Path $env:SystemRoot 'System32\msiexec.exe'
        $msiexecArguments = '/a "{0}" /qn /norestart TARGETDIR="{1}" /L*V "{2}"' -f `
            $msiPath, $extractRoot, $logPath
        $msiexecProcess = Start-Process `
            -FilePath $msiexec `
            -ArgumentList $msiexecArguments `
            -Wait `
            -PassThru `
            -NoNewWindow
        if ($msiexecProcess.ExitCode -ne 0) {
            $logSummary = if (Test-Path -LiteralPath $logPath) {
                (Get-Content -LiteralPath $logPath -Tail 30) -join [Environment]::NewLine
            }
            else {
                'No Windows Installer log was created.'
            }
            throw "eSpeak NG could not be extracted. MSI returned $($msiexecProcess.ExitCode). $logSummary"
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
        $sourceDownloaded = $false
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                Invoke-WebRequest `
                    -Uri 'https://github.com/espeak-ng/espeak-ng/archive/refs/tags/1.52.0.zip' `
                    -OutFile $sourceArchive `
                    -TimeoutSec 90
                $sourceDownloaded = $true
                break
            }
            catch {
                if (Test-Path -LiteralPath $sourceArchive) {
                    Remove-Item -LiteralPath $sourceArchive -Force
                }
                if ($attempt -eq 3) {
                    throw "eSpeak NG source download failed after $attempt attempts: $($_.Exception.Message)"
                }
                Start-Sleep -Seconds (5 * $attempt)
            }
        }
        if (-not $sourceDownloaded) {
            throw 'The eSpeak NG source archive could not be downloaded.'
        }
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
    foreach ($requiredLicense in @(
        'eSpeak-NG-COPYING.txt',
        'espeak-ng-1.52.0-source.zip',
        'Kokoro-82M-Apache-2.0.txt',
        'phonemizer-GPL-3.0.txt',
        'phonemizer-3.4.0-source.tar.gz',
        'THIRD_PARTY.md'
    )) {
        if ($requiredLicense -eq 'THIRD_PARTY.md') {
            $requiredPath = Join-Path $repoRoot $requiredLicense
        }
        else {
            $requiredPath = Join-Path (Join-Path $repoRoot 'licenses') $requiredLicense
        }
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "A required third-party license/source notice is missing: $requiredPath"
        }
    }
    $phonemizerSource = Join-Path $repoRoot 'licenses\phonemizer-3.4.0-source.tar.gz'
    $expectedPhonemizerSourceHash = 'E13231980C50BC671EC0466379BA027260AD9D61929952D8AE9665B3D0F251EB'
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $phonemizerSource).Hash -ne $expectedPhonemizerSourceHash) {
        throw 'The phonemizer source archive did not match the published SHA-256.'
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

    & $python -m pip install --disable-pip-version-check '-e' '.[build,test,natural]'
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
    & $python (Join-Path $PSScriptRoot 'smoke_languages.py')
    if ($LASTEXITCODE -ne 0) {
        throw 'A bundled language could not export a valid WAV.'
    }

    $engineDirArgument = "$engineRoot;bin\espeak-ng"
    $assetsArgument = "$(Join-Path $repoRoot 'assets');assets"
    $licensesArgument = "$(Join-Path $repoRoot 'licenses');licenses"
    $readmeLicenseArgument = "$(Join-Path $repoRoot 'THIRD_PARTY.md');licenses"
    $mitLicenseArgument = "$(Join-Path $repoRoot 'LICENSE');licenses"
    $iconArgument = Join-Path $repoRoot 'assets\classicvoice.ico'
    $entryPoint = Join-Path $repoRoot 'src\classicvoice\launcher.py'
    $specRoot = Join-Path $repoRoot 'build\spec'
    New-Item -ItemType Directory -Path $specRoot -Force | Out-Null
    $pyinstallerArgs = @(
        '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--onedir',
        '--name', 'ClassicVoice',
        '--specpath', $specRoot,
        '--icon', $iconArgument,
        '--paths', (Join-Path $repoRoot 'src'),
        '--add-data', $engineDirArgument,
        '--add-data', $assetsArgument,
        '--add-data', $licensesArgument,
        '--add-data', $readmeLicenseArgument,
        '--add-data', $mitLicenseArgument,
        '--collect-all', 'kokoro_onnx',
        '--collect-all', 'onnxruntime',
        '--collect-submodules', 'espeakng_loader',
        '--collect-all', 'phonemizer',
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
