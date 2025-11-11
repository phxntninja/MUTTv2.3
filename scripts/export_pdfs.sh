#!/usr/bin/env bash
set -euo pipefail

find_browser() {
  for c in google-chrome chrome chromium chromium-browser msedge; do
    if command -v "$c" >/dev/null 2>&1; then echo "$c"; return 0; fi
  done
  return 1
}

print_pdf() {
  local html="$1" out="$2" use_print="$3"
  local abs
  abs="$(cd "$(dirname "$html")" && pwd)/$(basename "$html")"
  local uri="file://$abs"
  [[ "$use_print" == "1" ]] && uri="$uri?print-pdf"
  local browser
  browser="$(find_browser)" || { echo "No Chromium-based browser found (chrome/chromium/msedge)." >&2; exit 1; }
  "$browser" --headless=old --disable-gpu --no-sandbox --print-to-pdf="$out" "$uri" >/dev/null
  echo "[ok] $out"
}

mkdir -p docs/slides

print_pdf docs/slides/ONE_PAGER.html docs/slides/ONE_PAGER.pdf 0
print_pdf docs/slides/mutt_v25_exec.html docs/slides/mutt_v25_exec.pdf 1
print_pdf docs/slides/mutt_v25_tech.html docs/slides/mutt_v25_tech.pdf 1

echo "All PDFs generated under docs/slides"

