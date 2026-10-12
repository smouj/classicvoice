param(
    [Parameter(Mandatory = $true)][int]$TargetProcessId,
    [Parameter(Mandatory = $true)][string]$WindowTitle,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class ClassicVoiceScreenshot {
    public delegate bool EnumCallback(IntPtr handle, IntPtr argument);
    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumCallback callback, IntPtr argument);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr handle, StringBuilder text, int length);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr handle, out uint process);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr handle, out Rect rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr handle, IntPtr destination, uint flags);
    public static IntPtr Find(int process, string title) {
        IntPtr result = IntPtr.Zero;
        int matches = 0;
        EnumWindows((handle, argument) => {
            uint owner;
            GetWindowThreadProcessId(handle, out owner);
            if (owner != process || !IsWindowVisible(handle)) return true;
            var text = new StringBuilder(1024);
            GetWindowText(handle, text, text.Capacity);
            if (text.ToString() == title) { result = handle; matches++; }
            return true;
        }, IntPtr.Zero);
        if (matches != 1) throw new InvalidOperationException("Expected exactly one visible window with the supplied process and title.");
        return result;
    }
}
'@

$cvHandle = [ClassicVoiceScreenshot]::Find($TargetProcessId, $WindowTitle)
$cvRect = New-Object ClassicVoiceScreenshot+Rect
if (-not [ClassicVoiceScreenshot]::GetClientRect($cvHandle, [ref]$cvRect)) {
    throw 'The window client bounds could not be read.'
}
$cvWidth = $cvRect.Right - $cvRect.Left
$cvHeight = $cvRect.Bottom - $cvRect.Top
if ($cvWidth -lt 200 -or $cvHeight -lt 200) { throw 'The window is too small or minimized.' }
$cvDestination = [IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $cvDestination) -Force | Out-Null
$cvBitmap = New-Object System.Drawing.Bitmap($cvWidth, $cvHeight)
$cvGraphics = [System.Drawing.Graphics]::FromImage($cvBitmap)
$cvHdc = $cvGraphics.GetHdc()
try {
    if (-not [ClassicVoiceScreenshot]::PrintWindow($cvHandle, $cvHdc, 1)) {
        throw 'Windows could not render the selected window for capture.'
    }
}
finally {
    $cvGraphics.ReleaseHdc($cvHdc)
    $cvGraphics.Dispose()
}
try { $cvBitmap.Save($cvDestination, [System.Drawing.Imaging.ImageFormat]::Png) }
finally { $cvBitmap.Dispose() }
Write-Output "$cvDestination ($cvWidth x $cvHeight)"
