#!/usr/bin/env bash
set -euo pipefail

echo "Checking generated PDFs under docs/slides"

shopt -s nullglob
files=(docs/slides/*.pdf)
shopt -u nullglob

if [ ${#files[@]} -eq 0 ]; then
  echo "No PDFs found in docs/slides" >&2
  exit 1
fi

have_pdftotext=0
if command -v pdftotext >/dev/null 2>&1; then
  have_pdftotext=1
fi

for f in "${files[@]}"; do
  # Size
  if stat -f %z "$f" >/dev/null 2>&1; then
    size=$(stat -f %z "$f")
    mtime=$(stat -f %Sm -t "%Y-%m-%d %H:%M:%S" "$f")
  else
    size=$(stat -c %s "$f")
    mtime=$(stat -c %y "$f" | cut -d. -f1)
  fi

  echo "--- $f"
  echo "Size: ${size} bytes"
  echo "Modified: ${mtime}"

  # Header check
  header=$(head -c 5 "$f" || true)
  if [[ "$header" == %PDF-* || "$header" == %PDF* ]]; then
    echo "Header: OK ($header)"
  else
    echo "Header: Unexpected ($header)" >&2
  fi

  # First-page text (best-effort)
  if [ "$have_pdftotext" -eq 1 ]; then
    echo "First-page text (truncated):"
    # Extract first page, trim to 300 chars for brevity
    txt=$(pdftotext -f 1 -l 1 "$f" - 2>/dev/null | sed -E 's/[[:cntrl:]]+/ /g' | tr -s ' ' | cut -c1-300 || true)
    if [ -n "$txt" ]; then
      echo "  $txt"
    else
      echo "  (no extractable text on first page or compressed)"
    fi
  else
    echo "pdftotext not found; skipping text extraction"
  fi
done

echo "Done."

