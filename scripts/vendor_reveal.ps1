param([string]$Version = '5.0.4')

$root = "docs/slides/vendor/reveal"
New-Item -ItemType Directory -Force -Path "$root/dist/theme" | Out-Null

$base = "https://unpkg.com/reveal.js@$Version/dist"

function Fetch($url, $out) {
  Write-Host "Downloading $url -> $out"
  Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $out
}

Fetch "$base/reveal.css" "$root/dist/reveal.css"
Fetch "$base/reveal.js" "$root/dist/reveal.js"
Fetch "$base/theme/white.css" "$root/dist/theme/white.css"
Fetch "$base/theme/black.css" "$root/dist/theme/black.css"

Write-Host "Done. Local assets under $root/dist"