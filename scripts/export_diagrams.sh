#!/usr/bin/env bash
set -euo pipefail

# Export SVG diagrams in docs/images to PNG for slide decks.
# Requires either: inkscape or rsvg-convert (librsvg2-bin).

SRC="docs/images/mutt-overview.svg"
OUT="docs/images/mutt-overview.png"
WIDTH=${WIDTH:-1920}

if command -v inkscape >/dev/null 2>&1; then
  echo "[export] Using Inkscape"
  inkscape "$SRC" --export-type=png --export-filename="$OUT" -w "$WIDTH"
elif command -v rsvg-convert >/dev/null 2>&1; then
  echo "[export] Using rsvg-convert"
  rsvg-convert -w "$WIDTH" -f png -o "$OUT" "$SRC"
else
  echo "Error: neither 'inkscape' nor 'rsvg-convert' is installed." >&2
  echo "Install Inkscape or librsvg (rsvg-convert) and re-run." >&2
  exit 1
fi

echo "Exported: $OUT"

