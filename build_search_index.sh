#!/bin/bash
# Rebuild the Pagefind full-text search index from all transcript pages.
# Run this once after all meetings for the day have been processed, e.g.:
#
#   python factory.py ... && python sync_meetings.py && \
#   python factory.py ... && python sync_meetings.py && \
#   ./build_search_index.sh && python upload_framework.py --target <bucket>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$SCRIPT_DIR/localhost"

echo "Building Pagefind index for: $SITE_DIR"
npx pagefind --site "$SITE_DIR" --output-path "$SITE_DIR/pagefind"
echo "Done. Index written to $SITE_DIR/pagefind/"
