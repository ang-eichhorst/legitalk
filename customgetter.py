#!/usr/bin/env python3
"""
Connecticut YouTube custom getter for SmartTranscripts.

- Reads committeeurl.json (committee -> channel_url)
- Uses yt-dlp to list the newest videos on each channel
- Skips anything already processed (tracked in ct_state.json)
- Calls factory.py for each new video

Run:
  python customgetter.py --max-per-committee 3 --dry-run
  python customgetter.py --max-per-committee 3
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

import yt_dlp

import re
from dateutil import parser as dateparser


ROOT = Path(__file__).resolve().parent
COMMITTEES_FILE = ROOT / "committeeurl.json"
STATE_FILE = ROOT / "ct_state.json"


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    

def parse_yt_date(upload_date: Optional[str]) -> Optional[str]:
    """
    yt-dlp upload_date is usually YYYYMMDD.
    Return ISO YYYY-MM-DD.
    """
    if not upload_date:
        return None
    try:
        d = dt.datetime.strptime(upload_date, "%Y%m%d").date()
        return d.isoformat()
    except Exception:
        return None

def extract_date_from_title(title: str):
    """
    Try to find a date in the video title.
    Returns ISO YYYY-MM-DD or None.
    """
    try:
        # fuzzy=True lets dateutil ignore extra words
        dt = dateparser.parse(title, fuzzy=True)
        if dt:
            return dt.date().isoformat()
    except Exception:
        pass
    return None

def list_recent_videos(channel_url: str, limit: int) -> List[Dict[str, Any]]:
    """
    Returns a list of dicts with keys: id, title, url, upload_date
    Uses yt-dlp "flat" extraction so it’s fast and doesn’t download media.
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,   # fast: only metadata
        "playlistend": limit,
    }

    videos: List[Dict[str, Any]] = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    # A channel /videos page is treated like a playlist.
    entries = info.get("entries") or []
    for e in entries:
        vid = e.get("id")
        if not vid:
            continue
        videos.append(
            {
                "id": vid,
                "title": e.get("title") or "",
                "url": e.get("url") or f"https://www.youtube.com/watch?v={vid}",
                "upload_date": parse_yt_date(e.get("upload_date")),
            }
        )
    return videos


def run_factory(url: str, committee: str, date_iso: str, jurisdiction: str, dry_run: bool) -> int:
    cmd = [
        sys.executable,
        str(ROOT / "factory.py"),
        "--url", url,
        "--committee", committee,
        "--date", date_iso,
        "--jurisdiction", jurisdiction,
    ]
    print("RUN:", " ".join(cmd))
    if dry_run:
        return 0
    p = subprocess.run(cmd)
    return p.returncode

def choose_best_date(title: str, upload_date_iso: Optional[str]) -> str:
    """
    Choose the best available date for a video:
    1) Date parsed from title
    2) YouTube upload_date (already ISO)
    3) Today (fallback)
    """
    title_date = extract_date_from_title(title)
    if title_date:
        return title_date

    if upload_date_iso:
        return upload_date_iso

    return dt.date.today().isoformat()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-committee", type=int, default=3, help="How many recent videos to scan per committee")
    ap.add_argument("--jurisdiction", default="Connecticut")
    ap.add_argument("--dry-run", action="store_true", help="Print what would run, but don’t run factory.py")
    args = ap.parse_args()

    committees = load_json(COMMITTEES_FILE, default=None)
    if not committees:
        print(f"Missing or empty {COMMITTEES_FILE}. Create it first.", file=sys.stderr)
        return 2

    state = load_json(STATE_FILE, default={"processed_video_ids": []})
    processed = set(state.get("processed_video_ids", []))

    newly_processed: List[str] = []

    for committee_name, cfg in committees.items():
        channel_url = cfg.get("channel_url")
        if not channel_url:
            print(f"SKIP {committee_name}: no channel_url in committeeurl.json", file=sys.stderr)
            continue

        print(f"\n=== {committee_name} ===")
        try:
            vids = list_recent_videos(channel_url, limit=args.max_per_committee)
        except Exception as e:
            print(f"FAIL listing videos for {committee_name}: {e}", file=sys.stderr)
            continue

        for v in vids:
            vid = v["id"]
            if vid in processed:
                print(f"Already processed: {vid}  {v['title'][:80]}")
                continue

            # If upload_date missing, fall back to today (keeps pipeline moving)
            date_iso = dt.date.today().isoformat()
            
            rc = run_factory(
                url=v["url"],
                committee=committee_name,
                date_iso=date_iso,
                jurisdiction=args.jurisdiction,
                dry_run=args.dry_run,
            )
            #date_iso = choose_best_date(
                #title=v["title"],
                #upload_date_iso=v.get("upload_date"),
            #)

            #rc = run_factory(
                #url=v["url"],
                #committee=committee_name,
                #date_iso=date_iso,
                #jurisdiction=args.jurisdiction,
                #dry_run=args.dry_run,
            #)
            
            if rc == 0:
                newly_processed.append(vid)
                processed.add(vid)
            else:
                print(f"Factory failed (rc={rc}) for video {vid}. Not marking as processed.", file=sys.stderr)

    if newly_processed and not args.dry_run:
        state["processed_video_ids"] = sorted(processed)
        save_json(STATE_FILE, state)
        print(f"\nSaved state to {STATE_FILE} (+{len(newly_processed)} new videos).")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
