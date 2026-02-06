#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run(cmd):
    print("RUN:", " ".join(cmd))
    return subprocess.run(cmd).returncode

def main():
    # Step 1: detect + process new meetings
    rc = run([
        sys.executable,
        str(ROOT / "customgetter.py"),
        "--max-per-committee", "1",
    ])

    if rc != 0:
        print("customgetter failed; not syncing to S3")
        return rc

    # Step 2: sync results to S3
    rc = run([
        sys.executable,
        str(ROOT / "sync_meetings.py"),
        "--source-dir", "localhost/meetings",
    ])

    return rc

if __name__ == "__main__":
    raise SystemExit(main())
