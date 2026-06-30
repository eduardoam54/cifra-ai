# Gera ícones PNG sólidos (laranja #ff6b35) sem dependências externas
Add-Type -AssemblyName System.Drawing

$color = [System.Drawing.Color]::FromArgb(255, 255, 107, 53)
$sizes = @(16, 32, 48, 128)
$outDir = $PSScriptRoot

foreach ($size in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $brush = New-Object System.Drawing.SolidBrush($color)
    $g.FillRectangle($brush, 0, 0, $size, $size)
    $g.Dispose()

    $path = Join-Path $outDir "icon$size.png"
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "Criado: $path"
}
