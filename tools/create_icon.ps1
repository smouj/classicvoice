param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,
    [string]$OutputPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'assets\classicvoice.ico')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$source = [System.Drawing.Bitmap]::new((Resolve-Path -LiteralPath $SourcePath).Path)
if ($source.Width -ne $source.Height) {
    $source.Dispose()
    throw 'The icon source must be square.'
}

$frames = [System.Collections.Generic.List[byte[]]]::new()
try {
    foreach ($size in @(16, 24, 32, 48, 64, 128, 256)) {
        $bitmap = [System.Drawing.Bitmap]::new(
            $size,
            $size,
            [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
        )
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

                # The supplied white mark is transparent. A compact purple tile
                # keeps it legible in Windows title bars and shortcut lists.
                $radius = [single]($size * 0.2)
                $tile = [System.Drawing.Drawing2D.GraphicsPath]::new()
                try {
                    $diameter = 2 * $radius
                    $tile.AddArc(0, 0, $diameter, $diameter, 180, 90)
                    $tile.AddArc(($size - $diameter), 0, $diameter, $diameter, 270, 90)
                    $tile.AddArc(($size - $diameter), ($size - $diameter), $diameter, $diameter, 0, 90)
                    $tile.AddArc(0, ($size - $diameter), $diameter, $diameter, 90, 90)
                    $tile.CloseFigure()
                    $brush = [System.Drawing.SolidBrush]::new(
                        [System.Drawing.Color]::FromArgb(81, 72, 229)
                    )
                    try { $graphics.FillPath($brush, $tile) }
                    finally { $brush.Dispose() }
                }
                finally {
                    $tile.Dispose()
                }
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
                $graphics.DrawImage($source, 0, 0, $size, $size)
            }
            finally {
                $graphics.Dispose()
            }

            $frameStream = [System.IO.MemoryStream]::new()
            $frameWriter = [System.IO.BinaryWriter]::new($frameStream)
            try {
                $frameWriter.Write([uint32]40)             # BITMAPINFOHEADER size
                $frameWriter.Write([int32]$size)           # Width
                $frameWriter.Write([int32]($size * 2))     # XOR image plus AND mask
                $frameWriter.Write([uint16]1)              # Planes
                $frameWriter.Write([uint16]32)             # BGRA
                $frameWriter.Write([uint32]0)              # BI_RGB
                $frameWriter.Write([uint32]($size * $size * 4))
                $frameWriter.Write([int32]0)
                $frameWriter.Write([int32]0)
                $frameWriter.Write([uint32]0)
                $frameWriter.Write([uint32]0)

                for ($y = $size - 1; $y -ge 0; $y--) {
                    for ($x = 0; $x -lt $size; $x++) {
                        $pixel = $bitmap.GetPixel($x, $y)
                        $frameWriter.Write([byte]$pixel.B)
                        $frameWriter.Write([byte]$pixel.G)
                        $frameWriter.Write([byte]$pixel.R)
                        $frameWriter.Write([byte]$pixel.A)
                    }
                }

                $maskRowBytes = [int]([Math]::Ceiling($size / 32.0) * 4)
                $mask = [byte[]]::new($maskRowBytes * $size)
                for ($y = 0; $y -lt $size; $y++) {
                    for ($x = 0; $x -lt $size; $x++) {
                        if ($bitmap.GetPixel($x, $y).A -lt 128) {
                            $mask[$y * $maskRowBytes + [int][Math]::Floor($x / 8.0)] =
                                $mask[$y * $maskRowBytes + [int][Math]::Floor($x / 8.0)] -bor
                                [byte](0x80 -shr ($x % 8))
                        }
                    }
                }
                $frameWriter.Write($mask)
                $frameWriter.Flush()
                $frames.Add($frameStream.ToArray())
            }
            finally {
                $frameWriter.Dispose()
                $frameStream.Dispose()
            }
        }
        finally {
            $bitmap.Dispose()
        }
    }
}
finally {
    $source.Dispose()
}

$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $outputFullPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$iconStream = [System.IO.File]::Open($outputFullPath, [System.IO.FileMode]::Create)
$iconWriter = [System.IO.BinaryWriter]::new($iconStream)
try {
    $iconWriter.Write([uint16]0) # Reserved
    $iconWriter.Write([uint16]1) # Icon resource
    $iconWriter.Write([uint16]$frames.Count)
    $nextOffset = 6 + (16 * $frames.Count)
    for ($index = 0; $index -lt $frames.Count; $index++) {
        $size = @(16, 24, 32, 48, 64, 128, 256)[$index]
        $directorySize = if ($size -eq 256) { 0 } else { $size }
        $iconWriter.Write([byte]$directorySize)
        $iconWriter.Write([byte]$directorySize)
        $iconWriter.Write([byte]0)
        $iconWriter.Write([byte]0)
        $iconWriter.Write([uint16]1)
        $iconWriter.Write([uint16]32)
        $iconWriter.Write([uint32]$frames[$index].Length)
        $iconWriter.Write([uint32]$nextOffset)
        $nextOffset += $frames[$index].Length
    }
    foreach ($frame in $frames) {
        $iconWriter.Write($frame)
    }
}
finally {
    $iconWriter.Dispose()
    $iconStream.Dispose()
}

Write-Host "Created multi-size Windows icon: $outputFullPath"
