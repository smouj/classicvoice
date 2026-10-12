param(
    [string]$BuildPath,
    [string]$Version
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($BuildPath)) {
    $releaseBuild = Join-Path $PSScriptRoot 'ClassicVoice'
    $repositoryBuild = Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\ClassicVoice'
    $BuildPath = if (Test-Path -LiteralPath $releaseBuild) { $releaseBuild } else { $repositoryBuild }
}
if ([string]::IsNullOrWhiteSpace($Version)) {
    $versionFile = Join-Path $PSScriptRoot 'VERSION.txt'
    $projectFile = Join-Path (Split-Path -Parent $PSScriptRoot) 'pyproject.toml'
    if (Test-Path -LiteralPath $versionFile) {
        $Version = (Get-Content -LiteralPath $versionFile -Raw).Trim()
    }
    elseif (Test-Path -LiteralPath $projectFile) {
        $projectToml = Get-Content -LiteralPath $projectFile -Raw
        if ($projectToml -match '(?ms)^\[project\].*?^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
            $Version = $Matches[1]
        }
    }
}
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw 'A stable semantic version could not be read from VERSION.txt or pyproject.toml.'
}

$resolvedBuild = (Resolve-Path -LiteralPath $BuildPath).Path
$appExe = Join-Path $resolvedBuild 'ClassicVoice.exe'
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "ClassicVoice.exe was not found in the build folder: $resolvedBuild"
}

$programsRoot = Join-Path $env:LOCALAPPDATA 'Programs'
$installRoot = [IO.Path]::GetFullPath((Join-Path $programsRoot 'ClassicVoice'))
$installParent = Split-Path -Parent $installRoot
New-Item -ItemType Directory -Path $installParent -Force | Out-Null

if (Get-Process -Name ClassicVoice -ErrorAction SilentlyContinue) {
    throw 'Close ClassicVoice before installing or updating it.'
}

$staging = Join-Path $installParent ('.ClassicVoice-staging-' + [guid]::NewGuid().ToString('N'))
$uninstallSources = @(
    (Join-Path $PSScriptRoot 'uninstall_windows.ps1'),
    (Join-Path $PSScriptRoot 'Uninstall-ClassicVoice.ps1')
)
$uninstallSource = $uninstallSources | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $uninstallSource) {
    throw 'The uninstaller script is missing from the installer package.'
}
try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    Copy-Item -Path (Join-Path $resolvedBuild '*') -Destination $staging -Recurse -Force
    Copy-Item -LiteralPath $uninstallSource -Destination (Join-Path $staging 'uninstall_windows.ps1') -Force

    if (-not (Test-Path -LiteralPath (Join-Path $staging 'ClassicVoice.exe'))) {
        throw 'The staged app is incomplete; the current installation has not been changed.'
    }

    $backupRoot = $null
    if (Test-Path -LiteralPath $installRoot) {
        $backupRoot = $installRoot + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Move-Item -LiteralPath $installRoot -Destination $backupRoot
    }

    try {
        Move-Item -LiteralPath $staging -Destination $installRoot
    }
    catch {
        if ($backupRoot -and (Test-Path -LiteralPath $backupRoot) -and -not (Test-Path -LiteralPath $installRoot)) {
            Move-Item -LiteralPath $backupRoot -Destination $installRoot
        }
        throw
    }
}
finally {
    if (Test-Path -LiteralPath $staging) {
        $resolvedParent = [IO.Path]::GetFullPath($installParent).TrimEnd('\')
        $resolvedStaging = [IO.Path]::GetFullPath($staging).TrimEnd('\')
        if (-not $resolvedStaging.StartsWith(($resolvedParent + '\.ClassicVoice-staging-'), [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean a staging folder outside the install parent: $resolvedStaging"
        }
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
}

$installedExe = Join-Path $installRoot 'ClassicVoice.exe'
$desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\ClassicVoice'
New-Item -ItemType Directory -Path $desktop -Force | Out-Null
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @(
    (Join-Path $desktop 'ClassicVoice.lnk'),
    (Join-Path $startMenu 'ClassicVoice.lnk')
)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $installedExe
    $shortcut.WorkingDirectory = $installRoot
    $shortcut.IconLocation = "$installedExe,0"
    $shortcut.Description = 'Texto a voz clásico en español'
    $shortcut.Save()
}

$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ClassicVoice'
New-Item -Path $uninstallKey -Force | Out-Null
$uninstallScript = Join-Path $installRoot 'uninstall_windows.ps1'
$uninstallCommand = 'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $uninstallScript + '"'
$sizeKb = [int]([math]::Ceiling(((Get-ChildItem -LiteralPath $installRoot -File -Recurse | Measure-Object Length -Sum).Sum) / 1KB))
Set-ItemProperty -LiteralPath $uninstallKey -Name DisplayName -Value 'ClassicVoice'
Set-ItemProperty -LiteralPath $uninstallKey -Name DisplayVersion -Value $Version
Set-ItemProperty -LiteralPath $uninstallKey -Name Publisher -Value 'smouj'
Set-ItemProperty -LiteralPath $uninstallKey -Name InstallLocation -Value $installRoot
Set-ItemProperty -LiteralPath $uninstallKey -Name DisplayIcon -Value "$installedExe,0"
Set-ItemProperty -LiteralPath $uninstallKey -Name UninstallString -Value $uninstallCommand
Set-ItemProperty -LiteralPath $uninstallKey -Name NoModify -Value 1 -Type DWord
Set-ItemProperty -LiteralPath $uninstallKey -Name NoRepair -Value 1 -Type DWord
Set-ItemProperty -LiteralPath $uninstallKey -Name EstimatedSize -Value $sizeKb -Type DWord

Write-Host "Installed ClassicVoice for this Windows user: $installRoot"
Write-Host "Desktop shortcut: $(Join-Path $desktop 'ClassicVoice.lnk')"
Write-Host "Start menu shortcut: $(Join-Path $startMenu 'ClassicVoice.lnk')"
Write-Host 'Settings and pronunciation rules are stored separately in LocalAppData and are preserved when uninstalling.'
