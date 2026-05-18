#!/bin/bash
# Rebuild Pagefind search indexes after adding new transcripts.
# Run this once at the end of the day after all meetings are processed.
#
# Usage:
#   ./build_search_index.sh           # builds both indexes
#   ./build_search_index.sh meetings  # meetings index only
#   ./build_search_index.sh other     # other index only

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$SCRIPT_DIR/localhost"
TARGET="${1:-both}"

if [[ "$TARGET" == "both" || "$TARGET" == "meetings" ]]; then
    echo "Building meetings index..."
    npx pagefind --site "$SITE_DIR" --output-path "$SITE_DIR/pagefind" --glob "meetings/**/*.html"
    echo "  → $SITE_DIR/pagefind/"
fi

if [[ "$TARGET" == "both" || "$TARGET" == "other" ]]; then
    echo "Building other index..."
    npx pagefind --site "$SITE_DIR" --output-path "$SITE_DIR/other/pagefind" --glob "other/**/*.html"
    echo "  → $SITE_DIR/other/pagefind/"
fi

echo "Done."
