"""Durable, single-user download queue. Requires Python 3.10+ and macOS."""

from __future__ import annotations

import base64
import binascii
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from . import model
from .metadata import choose_tags, find_artwork


DATA_DIR = Path.home() / "Library/Application Support/Share to Music"
SHORT_HOSTS = {"on.soundcloud.com", "soundcloud.app.goo.gl"}
SC_HOSTS = {"soundcloud.com", "www.soundcloud.com", "m.soundcloud.com"}
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
MAX_INPUT = 8192
MAX_DURATION = 7200
MAX_SIZE = 190_000_000
ACTIVE_STATES = ("resolving", "downloading", "importing")


class UserError(Exception):
    """An actionable error suitable for the CLI and saved job status."""


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value or len(value) > MAX_INPUT or any(c.isspace() or ord(c) < 32 for c in value):
        raise UserError("Share exactly one YouTube or SoundCloud track URL.")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise UserError("Invalid URL.") from exc
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        raise UserError("Use an HTTPS link without a username, password, or custom port.")
    if host in YT_HOSTS:
        path = parts.path.strip("/").split("/")
        video_id = ""
        if host == "youtu.be" and len(path) == 1:
            video_id = path[0]
        elif parts.path == "/watch":
            video_id = parse_qs(parts.query).get("v", [""])[0]
        elif len(path) == 2 and path[0] in {"shorts", "live", "embed"}:
            video_id = path[1]
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise UserError("Use a single YouTube video link, not a channel or playlist.")
        return f"https://www.youtube.com/watch?v={video_id}"
    if host in SC_HOSTS:
        path = parts.path.strip("/").split("/")
        if len(path) not in (2, 3) or path[1] in {
            "sets", "tracks", "albums", "likes", "reposts", "spotlight", "comments"
        } or path[0] in {"discover", "stations", "search", "you"}:
            raise UserError("Use one SoundCloud track link, not a profile, set, or playlist.")
        if any(not re.fullmatch(r"[A-Za-z0-9_-]+", piece) for piece in path):
            raise UserError("Invalid SoundCloud track link.")
        # Keep private-track access tokens, but remove tracking parameters.
        query = parse_qs(parts.query).get("secret_token", [])
        return urlunsplit(("https", "soundcloud.com", "/" + "/".join(path),
                           urlencode({"secret_token": query[0]}) if query else "", ""))
    if host in SHORT_HOSTS and re.fullmatch(r"/[A-Za-z0-9_-]+/?", parts.path):
        return urlunsplit(("https", host, parts.path.rstrip("/"), "", ""))
    raise UserError("Supported links: youtube.com, youtu.be, and SoundCloud track/share links.")


def decode_url(encoded: str) -> str:
    if len(encoded) > MAX_INPUT * 2:
        raise UserError("Shared input is too large.")
    try:
        return base64.b64decode("".join(encoded.split()), validate=True).decode("utf-8")
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise UserError("Invalid Base64 input. Check the Shortcut's Encode action.") from exc


class SoundCloudRedirects(HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        normalized = normalize_url(target)
        if urlsplit(normalized).hostname not in SC_HOSTS | SHORT_HOSTS:
            raise UserError("SoundCloud share link redirected outside SoundCloud.")
        return super().redirect_request(req, fp, code, msg, headers, normalized)


def resolve_short_link(url: str) -> str:
    if urlsplit(url).hostname not in SHORT_HOSTS:
        return url
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with build_opener(SoundCloudRedirects()).open(request, timeout=20) as response:
            result = normalize_url(response.url)
    except (OSError, ValueError) as exc:
        raise UserError("Could not resolve SoundCloud share link. Try the full track URL.") from exc
    if urlsplit(result).hostname in SHORT_HOSTS:
        raise UserError("This share link did not resolve. Share the full soundcloud.com track URL.")
    return result


def connect(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(root / "queue.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
        created REAL NOT NULL, updated REAL NOT NULL, title TEXT, media_key TEXT,
        audio_path TEXT, music_id TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0
    )""")
    db.commit()
    return db


def update(db: sqlite3.Connection, job_id: str, **values) -> None:
    values["updated"] = time.time()
    with db:
        db.execute(f"UPDATE jobs SET {', '.join(key + '=?' for key in values)} WHERE id=?",
                   [*values.values(), job_id])


def enqueue(db: sqlite3.Connection, url: str) -> sqlite3.Row:
    url = normalize_url(url)
    now = time.time()
    with db:
        db.execute("INSERT OR IGNORE INTO jobs (id,url,state,created,updated) VALUES (?,?,?,?,?)",
                   (uuid.uuid4().hex[:12], url, "queued", now, now))
    return db.execute("SELECT * FROM jobs WHERE url=?", (url,)).fetchone()


def retry(db: sqlite3.Connection, job_id: str) -> None:
    with db:
        changed = db.execute("UPDATE jobs SET state='queued', error=NULL, updated=? "
                             "WHERE id=? AND state='failed'", (time.time(), job_id)).rowcount
    if not changed:
        raise UserError("Only failed jobs can be retried. Use status to find the job ID.")


def run_command(args: list[str], *, timeout: int, log=None) -> str:
    """No shell expansion; kill the entire tool process group on timeout."""
    process = subprocess.Popen(args, stdout=log or subprocess.PIPE, stderr=log or subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        import signal

        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise UserError(f"{Path(args[0]).name} timed out or was interrupted. See the job log.")
    if process.returncode:
        detail = (stderr or "See the job log for details.").strip()[-1600:]
        raise UserError(f"{Path(args[0]).name} failed: {detail}")
    return stdout or ""


def downloader_args() -> list[str]:
    return ["yt-dlp", "--ignore-config", "--no-plugin-dirs", "--no-playlist",
            "--no-progress", "--no-warnings", "--socket-timeout", "20", "--retries", "3",
            "--extractor-retries", "3", "--use-extractors", "youtube,soundcloud"]


def inspect_media(url: str) -> dict:
    info = json.loads(run_command([*downloader_args(), "--dump-single-json", "--", url], timeout=180))
    if info.get("_type", "video") != "video" or info.get("entries") is not None:
        raise UserError("Only individual tracks/videos are supported.")
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise UserError("Live/upcoming streams are unsupported; wait for a finished upload.")
    duration = info.get("duration")
    if not isinstance(duration, (float, int)) or not 0 < duration <= MAX_DURATION:
        raise UserError("The track must have a known duration of at most two hours.")
    extractor = str(info.get("extractor_key", "")).lower()
    if extractor not in {"youtube", "soundcloud"} or not re.fullmatch(r"[\w-]+", str(info.get("id", ""))):
        raise UserError("Unexpected media source or ID.")
    return info


def media_key(info: dict) -> str:
    return f"{info['extractor_key'].lower()}:{info['id']}"


def download_audio(root: Path, job: sqlite3.Row, info: dict, url: str, log) -> Path:
    key = media_key(info)
    output = root / "audio" / (hashlib.sha256(key.encode()).hexdigest()[:24] + ".m4a")
    output.parent.mkdir(exist_ok=True)
    if output.exists():
        return output
    staging = root / "staging" / job["id"]
    staging.mkdir(parents=True, exist_ok=True)
    manifest = staging / "download.jsonl"
    manifest.unlink(missing_ok=True)
    run_command([*downloader_args(), "--format", "bestaudio/best", "--max-filesize", "250M",
                 "--match-filter", f"!is_live & duration <= {MAX_DURATION}",
                 "--output", str(staging / "source.%(ext)s"),
                 "--print-to-file", "after_move:%()j", str(manifest), "--", url],
                timeout=1200, log=log)
    if not manifest.exists():
        raise UserError("No audio downloaded. The source may exceed the download limits.")
    entries = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    if len(entries) != 1 or media_key(entries[0]) != key:
        raise UserError("Download did not match the requested track.")
    source = Path(entries[0]["filepath"]).resolve()
    if not source.is_relative_to(staging.resolve()) or not source.is_file():
        raise UserError("Downloader returned an unexpected file path.")
    temporary = output.with_suffix(".partial.m4a")
    suggestion = model.suggest(root, info, staging, log, run_command)
    tags = choose_tags(info, suggestion)
    log.write(f"Selected tags: {json.dumps(tags, ensure_ascii=False)}\n")
    run_command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
                 "-map", "0:a:0", "-vn", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
                 "-metadata", f"title={tags['title']}", "-metadata", f"artist={tags['artist']}",
                 "-metadata", f"album={tags['album']}",
                 "-metadata", f"comment=share-to-music:{key}", str(temporary)],
                timeout=600, log=log)
    if not temporary.exists() or not 0 < temporary.stat().st_size <= MAX_SIZE:
        temporary.unlink(missing_ok=True)
        raise UserError("Converted audio exceeds the 190 MB limit or is empty.")
    probe = json.loads(run_command(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "json", str(temporary)], timeout=20))
    if not 0 < float(probe["format"]["duration"]) <= MAX_DURATION + 1:
        temporary.unlink(missing_ok=True)
        raise UserError("Converted audio has an invalid duration.")
    # Keep the valid audio until optional image retrieval AND embedding succeed.
    try:
        cover, album = find_artwork(tags, info, staging, log, run_command)
        if cover:
            decorated = staging / "with-artwork.m4a"
            run_command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                         "-i", str(temporary), "-i", str(cover),
                         "-map", "0:a:0", "-map", "1:v:0", "-map_metadata", "0",
                         "-c:a", "copy", "-c:v", "mjpeg", "-disposition:v", "attached_pic",
                         "-metadata", f"album={album or tags['album']}", "-movflags", "+faststart",
                         str(decorated)], timeout=30, log=log)
            check = json.loads(run_command(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                                            "-of", "json", str(decorated)], timeout=10))
            streams = check.get("streams", [])
            if (not any(s.get("disposition", {}).get("attached_pic") == 1 for s in streams)
                    or not any(s.get("codec_name") == "aac" for s in streams)
                    or check.get("format", {}).get("tags", {}).get("comment") != f"share-to-music:{key}"
                    or not 0 < decorated.stat().st_size <= MAX_SIZE):
                raise ValueError("Artwork output failed validation")
            decorated.replace(temporary)
    except Exception as exc:
        log.write(f"Artwork unavailable ({type(exc).__name__}); importing audio without new artwork.\n")
    temporary.replace(output)
    shutil.rmtree(staging)
    return output


def import_music(path: Path, key: str) -> str:
    script = Path(__file__).with_name("import.applescript")
    return run_command(["/usr/bin/osascript", str(script), str(path), f"share-to-music:{key}"],
                       timeout=180).strip()


def process_queue(root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        with contextlib.closing(connect(root)) as db:
            # Holding the OS lock proves there is no live previous worker.
            with db:
                db.execute("UPDATE jobs SET state='queued' WHERE state IN (?,?,?)", ACTIVE_STATES)
            while job := db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone():
                logs = root / "logs"
                logs.mkdir(exist_ok=True)
                update(db, job["id"], state="resolving", attempts=job["attempts"] + 1, error=None)
                with (logs / f"{job['id']}.log").open("a", buffering=1) as log:
                    try:
                        key, audio = job["media_key"], job["audio_path"]
                        if not key or not audio or not Path(audio).is_file():
                            url = resolve_short_link(job["url"])
                            info = inspect_media(url)
                            key = media_key(info)
                            update(db, job["id"], title=info.get("title"), media_key=key, state="downloading")
                            audio = str(download_audio(root, job, info, url, log))
                            update(db, job["id"], audio_path=audio)
                        update(db, job["id"], state="importing")
                        music_id = import_music(Path(audio), key)
                        if not re.fullmatch(r"[0-9A-Fa-f]{16}", music_id):
                            raise UserError("Music did not confirm the import. Check Music on the Mac, then retry.")
                        update(db, job["id"], state="complete", music_id=music_id)
                    except Exception as exc:
                        log.write(f"\n{type(exc).__name__}: {exc}\n")
                        update(db, job["id"], state="failed", error=str(exc)[:2000])
    return 0
