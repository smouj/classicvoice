$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$installRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSCommandPath)).TrimEnd('\')
$expectedRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\ClassicVoice')).TrimEnd('\')
if (-not $installRoot.Equals($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove an unexpected path: $installRoot"
}

$answer = [System.Windows.Forms.MessageBox]::Show(
    '¿Desinstalar ClassicVoice? Tus ajustes y reglas de pronunciación se conservarán.',
    'Desinstalar ClassicVoice',
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Question
)
if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
    exit 0
}

if (Get-Process -Name ClassicVoice -ErrorAction SilentlyContinue) {
    [System.Windows.Forms.MessageBox]::Show(
        'Cierra ClassicVoice y vuelve a iniciar la desinstalación.',
        'ClassicVoice sigue abierto',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
    exit 1
}

$expectedExe = Join-Path $installRoot 'ClassicVoice.exe'
$desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\ClassicVoice'
$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @(
    (Join-Path $desktop 'ClassicVoice.lnk'),
    (Join-Path $startMenu 'ClassicVoice.lnk')
)) {
    if (Test-Path -LiteralPath $shortcutPath) {
        $shortcut = $shell.CreateShortcut($shortcutPath)
        if ([IO.Path]::GetFullPath($shortcut.TargetPath).Equals($expectedExe, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $shortcutPath -Force
        }
    }
}
if ((Test-Path -LiteralPath $startMenu) -and
    -not (Get-ChildItem -LiteralPath $startMenu -Force | Select-Object -First 1)) {
    Remove-Item -LiteralPath $startMenu -Force
}

$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ClassicVoice'
if (Test-Path -LiteralPath $uninstallKey) {
    Remove-Item -LiteralPath $uninstallKey -Recurse -Force
}

if ([IO.Path]::GetFullPath($installRoot).Equals($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
}

[System.Windows.Forms.MessageBox]::Show(
    'ClassicVoice se ha desinstalado. Tus ajustes y tus archivos WAV siguen en su sitio.',
    'ClassicVoice desinstalado',
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null
