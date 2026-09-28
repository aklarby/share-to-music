from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import __version__
from .core import DATA_DIR, UserError, connect, decode_url, enqueue, process_queue, retry


def main(argv=None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Send YouTube/SoundCloud audio to Music on your Mac.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Override private queue/audio directory")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("enqueue", help="Queue one URL; returns immediately")
    source = add.add_mutually_exclusive_group(required=True)
    source.add_argument("url", nargs="?")
    source.add_argument("--base64", dest="encoded", help="Base64 encoded URL from Shortcuts")
    status = sub.add_parser("status", help="Show recent jobs or one job")
    status.add_argument("job_id", nargs="?")
    status.add_argument("--json", action="store_true")
    again = sub.add_parser("retry", help="Retry a failed job; reuse converted audio when available")
    again.add_argument("job_id")
    sub.add_parser("worker", help="Process queued jobs (normally run by launchd)")
    doctor = sub.add_parser("doctor", help="Check dependencies and background worker")
    doctor.add_argument("--music", action="store_true", help="Ask Music for its version; may request Automation permission")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            ok = sys.platform == "darwin"
            print(f"{'OK' if ok else 'MISSING'} macOS")
            for tool in ("yt-dlp", "ffmpeg", "ffprobe", "deno"):
                location = shutil.which(tool)
                print(f"{'OK' if location else 'MISSING'} {tool}: {location or 'brew install yt-dlp ffmpeg deno'}")
                ok = ok and bool(location)
            service = subprocess.run(["/bin/launchctl", "print", f"gui/{os.getuid()}/com.share-to-music.worker"],
                                     capture_output=True) if sys.platform == "darwin" else None
            loaded = service is not None and service.returncode == 0
            print(f"{'OK' if loaded else 'MISSING'} background worker: {'loaded' if loaded else 'run python3 scripts/install.py'}")
            ok = ok and loaded
            if args.music and sys.platform == "darwin":
                result = subprocess.run(["/usr/bin/osascript", "-e", 'tell application "Music" to get version'],
                                        text=True, capture_output=True, timeout=30)
                print(f"{'OK' if result.returncode == 0 else 'FAILED'} Music: {(result.stdout or result.stderr).strip()}")
                ok = ok and result.returncode == 0
            print("Phone/cloud sync is managed by Music; this check cannot verify it.")
            return 0 if ok else 1
        if args.command == "worker":
            return process_queue(args.data_dir)
        with contextlib.closing(connect(args.data_dir)) as db:
            if args.command == "enqueue":
                job = enqueue(db, decode_url(args.encoded) if args.encoded is not None else args.url)
                if job["state"] == "failed":
                    print(f"Failed earlier: {job['id']}. Run share-to-music retry {job['id']} after checking status.")
                    return 1
                if job["state"] == "complete":
                    print(f"Already imported into Music: {job['id']}. Phone sync is handled by Music.")
                else:
                    print(f"Queued on Mac: {job['id']} ({job['state']}). Import and phone sync happen afterward.")
            elif args.command == "retry":
                retry(db, args.job_id)
                print(f"Queued retry: {args.job_id}")
            else:
                jobs = db.execute("SELECT * FROM jobs WHERE id=?", (args.job_id,)).fetchall() if args.job_id else db.execute(
                    "SELECT * FROM jobs ORDER BY created DESC LIMIT 20").fetchall()
                if args.job_id and not jobs:
                    raise UserError("Job not found.")
                if args.json:
                    print(json.dumps([dict(job) for job in jobs], indent=2))
                elif not jobs:
                    print("No jobs yet. Share a link or run share-to-music enqueue URL.")
                for job in [] if args.json else jobs:
                    print(f"{job['id']}  {job['state']:<11} {job['title'] or '(title pending)'}")
                    if job["error"]:
                        print(f"  {job['error']}")
                    if args.job_id:
                        print(f"  Log: {args.data_dir / 'logs' / (job['id'] + '.log')}")
        return 0
    except (UserError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
