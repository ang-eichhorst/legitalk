"""
One-off script: add Pagefind attributes to all existing transcript.html files.

For each localhost/meetings/{Committee}/{Date}/transcript.html:
  1. Adds data-pagefind-body to <div id="text-container">
  2. Injects hidden meta divs for committee, date, and speakers before </body>
  3. Adds a Search link to the header (matching viewer_template.html change)

Safe to re-run — skips files that already have the attributes.
"""

import os
import re
from pathlib import Path

MEETINGS_DIR = Path(__file__).parent / "localhost" / "meetings"


def extract_speakers(text: str) -> str:
    """Extract unique speaker names from <strong>[Name]:</strong> tags."""
    names = re.findall(r'<strong>\[([^\]]+)\]:</strong>', text)
    seen = {}
    for name in names:
        if name not in seen:
            seen[name] = True
    return ', '.join(seen.keys())


def patch_file(path: Path, committee_name: str, date_str: str) -> bool:
    """Patch a single transcript.html. Returns True if the file was modified."""
    text = path.read_text(encoding="utf-8")
    changed = False

    # 1. Add data-pagefind-body to text-container (if not already present)
    old = '<div id="text-container">'
    new = '<div id="text-container" data-pagefind-body>'
    if old in text:
        text = text.replace(old, new, 1)
        changed = True

    # 2. Inject hidden meta tags before </body> (if not already present)
    if 'data-pagefind-meta="committee"' not in text:
        speakers = extract_speakers(text)
        meta_block = (
            f'    <div data-pagefind-meta="committee" style="display:none">{committee_name}</div>\n'
            f'    <div data-pagefind-meta="date" style="display:none">{date_str}</div>\n'
            f'    <div data-pagefind-meta="speakers" style="display:none">{speakers}</div>\n'
        )
        text = text.replace("</body>", meta_block + "</body>", 1)
        changed = True
    elif 'data-pagefind-meta="date"' not in text:
        # committee tag exists but date/speakers were added later — patch them in
        speakers = extract_speakers(text)
        extra = (
            f'    <div data-pagefind-meta="date" style="display:none">{date_str}</div>\n'
            f'    <div data-pagefind-meta="speakers" style="display:none">{speakers}</div>\n'
        )
        text = text.replace("</body>", extra + "</body>", 1)
        changed = True

    # 3. Add Search link to header (if not already present)
    search_link = '<a href="/search.html" style="margin-left:1rem;font-size:0.9rem;white-space:nowrap;">Search</a>'
    if search_link not in text:
        text = re.sub(
            r'(<h2 id="meeting-title">[^<]*</h2>)',
            r'\1\n                ' + search_link,
            text,
            count=1,
        )
        changed = True

    if changed:
        path.write_text(text, encoding="utf-8")

    return changed


def main():
    if not MEETINGS_DIR.exists():
        print(f"Meetings directory not found: {MEETINGS_DIR}")
        return

    patched = 0
    skipped = 0

    for transcript in sorted(MEETINGS_DIR.rglob("transcript.html")):
        try:
            rel = transcript.relative_to(MEETINGS_DIR)
            committee_folder = rel.parts[0]
            date_folder = rel.parts[1] if len(rel.parts) > 2 else ''
            committee_name = committee_folder.replace("_", " ")
            date_str = date_folder
        except (ValueError, IndexError):
            committee_name = "Unknown Committee"
            date_str = ""

        if patch_file(transcript, committee_name, date_str):
            print(f"  Patched: {transcript.relative_to(MEETINGS_DIR.parent.parent)}")
            patched += 1
        else:
            skipped += 1

    print(f"\nDone. Patched {patched} files, skipped {skipped} (already up-to-date).")


if __name__ == "__main__":
    main()
