#!/usr/bin/env bash
set -euo pipefail

find_browser() {
  if [ -n "${BROWSER:-}" ] && [ -x "$BROWSER" ]; then
    echo "$BROWSER"; return 0
  fi
  uname_s="$(uname -s 2>/dev/null || echo unknown)"
  if [ "$uname_s" = "Darwin" ]; then
    # Common macOS app bundle paths
    local mac_candidates=(
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
      "/Applications/Chromium.app/Contents/MacOS/Chromium"
      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    )
    for c in "${mac_candidates[@]}"; do
      if [ -x "$c" ]; then echo "$c"; return 0; fi
    done
  fi
  # Fallback to PATH on Linux or if macOS apps not found
  for c in google-chrome chrome chromium chromium-browser msedge microsoft-edge; do
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
  "$browser" --headless --disable-gpu --no-sandbox --print-to-pdf="$out" "$uri" >/dev/null
  echo "[ok] $out"
}

mkdir -p docs/slides

print_pdf docs/slides/ONE_PAGER.html docs/slides/ONE_PAGER.pdf 0

# Prefer offline decks if present
exec_html="docs/slides/mutt_v25_exec.html"
tech_html="docs/slides/mutt_v25_tech.html"
[ -f docs/slides/mutt_v25_exec_offline.html ] && exec_html="docs/slides/mutt_v25_exec_offline.html"
[ -f docs/slides/mutt_v25_tech_offline.html ] && tech_html="docs/slides/mutt_v25_tech_offline.html"

print_pdf "$exec_html" docs/slides/mutt_v25_exec.pdf 1
print_pdf "$tech_html" docs/slides/mutt_v25_tech.pdf 1

echo "All PDFs generated under docs/slides"
