param(
  [switch]$VerboseMode
)

function Find-Browser {
  # Allow explicit override via env var
  if ($env:BROWSER -and (Test-Path $env:BROWSER)) { return $env:BROWSER }

  $candidates = @('msedge', 'chrome', 'google-chrome', 'chromium', 'chromium-browser')
  foreach ($c in $candidates) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Path }
  }

  # Common Windows install paths
  $paths = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
    "$env:LocalAppData\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
  )
  foreach ($p in $paths) { if (Test-Path $p) { return $p } }
  return $null
}

function Print-Pdf([string]$htmlPath, [string]$pdfPath, [switch]$UsePrintQuery) {
  $absHtml = Resolve-Path $htmlPath
  $uri = "file:///" + ($absHtml -replace '\\','/').TrimStart('/')
  if ($UsePrintQuery) { $uri = "$uri?print-pdf" }
  $browser = Find-Browser
  if (-not $browser) { throw "No Chromium-based browser found (msedge/chrome)." }
  # Ensure absolute output path for Chrome
  $pdfAbs = $pdfPath
  try {
    $resolved = Resolve-Path $pdfPath -ErrorAction Stop
    $pdfAbs = $resolved.Path
  } catch {
    $pdfAbs = Join-Path (Resolve-Path .) $pdfPath
  }
  if ($VerboseMode) { Write-Host "[pdf] $browser --headless --print-to-pdf=$pdfAbs $uri" }
  & $browser --headless --disable-gpu --no-sandbox --print-to-pdf="$pdfAbs" "$uri" | Out-Null
  if (-not (Test-Path $pdfAbs)) { throw "PDF export failed or file not created: $pdfAbs" }
  Write-Host "[ok] $pdfPath"
}

New-Item -ItemType Directory -Force -Path docs/slides | Out-Null

Print-Pdf -htmlPath "docs/slides/ONE_PAGER.html" -pdfPath "docs/slides/ONE_PAGER.pdf"

# Prefer offline decks if present (PowerShell-compatible selection)
if (Test-Path "docs/slides/mutt_v25_exec_offline.html") {
  $execHtml = "docs/slides/mutt_v25_exec_offline.html"
} else {
  $execHtml = "docs/slides/mutt_v25_exec.html"
}

if (Test-Path "docs/slides/mutt_v25_tech_offline.html") {
  $techHtml = "docs/slides/mutt_v25_tech_offline.html"
} else {
  $techHtml = "docs/slides/mutt_v25_tech.html"
}

Print-Pdf -htmlPath $execHtml -pdfPath "docs/slides/mutt_v25_exec.pdf" -UsePrintQuery
Print-Pdf -htmlPath $techHtml -pdfPath "docs/slides/mutt_v25_tech.pdf" -UsePrintQuery

Write-Host "All PDFs generated under docs/slides" -ForegroundColor Green
