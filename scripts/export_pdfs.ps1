param(
  [switch]$VerboseMode
)

function Find-Browser {
  $candidates = @('msedge', 'chrome', 'google-chrome', 'chromium', 'chromium-browser')
  foreach ($c in $candidates) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Path }
  }
  return $null
}

function Print-Pdf([string]$htmlPath, [string]$pdfPath, [switch]$UsePrintQuery) {
  $abs = Resolve-Path $htmlPath
  $uri = "file:///" + ($abs -replace '\\','/').TrimStart('/')
  if ($UsePrintQuery) { $uri = "$uri?print-pdf" }
  $browser = Find-Browser
  if (-not $browser) { throw "No Chromium-based browser found (msedge/chrome)." }
  if ($VerboseMode) { Write-Host "[pdf] $browser --headless --print-to-pdf=$pdfPath $uri" }
  & $browser --headless=old --disable-gpu --no-sandbox --print-to-pdf="$pdfPath" "$uri" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "PDF export failed for $htmlPath" }
  Write-Host "[ok] $pdfPath"
}

New-Item -ItemType Directory -Force -Path docs/slides | Out-Null

Print-Pdf -htmlPath "docs/slides/ONE_PAGER.html" -pdfPath "docs/slides/ONE_PAGER.pdf"
Print-Pdf -htmlPath "docs/slides/mutt_v25_exec.html" -pdfPath "docs/slides/mutt_v25_exec.pdf" -UsePrintQuery
Print-Pdf -htmlPath "docs/slides/mutt_v25_tech.html" -pdfPath "docs/slides/mutt_v25_tech.pdf" -UsePrintQuery

Write-Host "All PDFs generated under docs/slides" -ForegroundColor Green

