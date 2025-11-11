#!/usr/bin/env bash
set -euo pipefail

VER="5.0.4"
ROOT="docs/slides/vendor/reveal"
mkdir -p "$ROOT/dist/theme"

base="https://unpkg.com/reveal.js@${VER}/dist"

echo "Downloading Reveal.js ${VER} assets..."
curl -fsSL "$base/reveal.css" -o "$ROOT/dist/reveal.css"
curl -fsSL "$base/reveal.js" -o "$ROOT/dist/reveal.js"
curl -fsSL "$base/theme/white.css" -o "$ROOT/dist/theme/white.css"
curl -fsSL "$base/theme/black.css" -o "$ROOT/dist/theme/black.css"

echo "Done. Local assets under $ROOT/dist"

