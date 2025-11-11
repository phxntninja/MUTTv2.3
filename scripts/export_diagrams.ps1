param([
  int]$Width = 1920
)

$src = "docs/images/mutt-overview.svg"
$out = "docs/images/mutt-overview.png"

function Has-Cmd($name) { $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

if (Has-Cmd inkscape) {
  Write-Host "[export] Using Inkscape"
  inkscape $src --export-type=png --export-filename=$out -w $Width
}
elseif (Has-Cmd rsvg-convert) {
  Write-Host "[export] Using rsvg-convert"
  rsvg-convert -w $Width -f png -o $out $src
}
else {
  Write-Error "Neither 'inkscape' nor 'rsvg-convert' is installed. Install one to export PNG."
  exit 1
}

Write-Host "Exported: $out"