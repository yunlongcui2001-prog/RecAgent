#!/usr/bin/env bash
set -euo pipefail

# Amazon Beauty 5-core, McAuley dataset dump (2014).
URL="https://snap.stanford.edu/data/amazon/productGraph/categoryFiles/reviews_Beauty_5.json.gz"
DEST_DIR="$(dirname "$0")/../data/raw"
DEST_FILE="$DEST_DIR/reviews_Beauty_5.json.gz"

mkdir -p "$DEST_DIR"

if [[ -f "$DEST_FILE" ]]; then
  echo "[skip] $DEST_FILE already exists"
  exit 0
fi

echo "[download] $URL"
curl -L --fail --progress-bar -o "$DEST_FILE" "$URL"
echo "[done] saved to $DEST_FILE"