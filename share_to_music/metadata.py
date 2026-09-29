"""Conservative tag cleanup and bounded artwork retrieval from known image CDNs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_IMAGE = 5_000_000
VARIANTS = ("unreleased", "live", "remix", "cover", "instrumental", "sped up", "slowed", "reverb",
            "acoustic", "demo", "edit", "mix", "version", "nightcore", "extended", "remaster", "remastered")
IMAGE_HOSTS = ("sndcdn.com", "ytimg.com")


def clean_text(value, limit=300):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 and not c.isspace() for c in value):
        return ""
    return " ".join(value.split()).strip()


def clean_title(value):
    value = clean_text(value)
    value = re.sub(r"\.(?:mp3|m4a|wav|flac|aac|mp4|webm)$", "", value, flags=re.I).strip()
    # Source fallbacks also omit upload/recording labels from display names.
    def label(match):
        body = match.group(1)
        promotional = re.fullmatch(r"(?:official\s+)?(?:audio|music video|video|lyric video|lyrics)", body, re.I)
        return " " if promotional or versions(body) else match.group(0)
    value = re.sub(r"[\[(]([^\])]+)[\])]", label, value)
    labels = "|".join(re.escape(word) for word in VARIANTS)
    value = re.sub(r"\s+[|–—-]\s*(?:" + labels + r")\b.*$", "", value, flags=re.I)
    return " ".join(value.split()).strip()


def versions(value):
    return {word for word in VARIANTS if re.search(r"(?<!\w)" + word + r"(?!\w)", value, re.I)}


def model_tags(value):
    """Use the model's names directly; missing or malformed fields use source tags."""
    if isinstance(value, str):
        if len(value) > 8192:
            return {}
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.I)
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    if not isinstance(value, dict):
        return {}
    title, artist = clean_text(value.get("title")), clean_text(value.get("artist"))
    return {key: text for key, text in (("title", title), ("artist", artist)) if text}


def choose_tags(info, suggestion=None):
    title = clean_title(info.get("track") or info.get("title")) or "Shared audio"
    artist = clean_text(info.get("artist") or info.get("uploader")) or "Unknown artist"
    proposed = model_tags(suggestion)
    title = proposed.get("title") or title
    artist = proposed.get("artist") or artist
    return {"title": title, "artist": artist, "album": "SoundCloud",
            "album_artist": "Various Artists", "compilation": "1"}


def allowed_url(url):
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("Invalid artwork URL")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Artwork requires HTTPS without credentials or a custom port")
    if not any(host == domain or host.endswith("." + domain) for domain in IMAGE_HOSTS):
        raise ValueError("Artwork host is not allowed")
    return url


class SafeRedirects(HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    allowed_url(url)
    request = Request(url, headers={"User-Agent": "ShareToMusic/0.2", "Accept": "image/*"})
    deadline = time.monotonic() + 10
    with build_opener(SafeRedirects()).open(request, timeout=5) as response:
        allowed_url(response.url)
        content_type = response.headers.get_content_type()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Unsupported artwork content type")
        chunks, size = [], 0
        while size <= MAX_IMAGE:
            if time.monotonic() > deadline:
                raise TimeoutError("Artwork response timed out")
            chunk = response.read1(min(65536, MAX_IMAGE + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        data = b"".join(chunks)
        if not data or len(data) > MAX_IMAGE:
            raise ValueError("Artwork response is empty or too large")
        return data


def find_artwork(info, directory: Path, log, run_command):
    """Use only the upload's images; a missing image never fails the audio job."""
    thumbnails = info.get("thumbnails") or []
    if not isinstance(thumbnails, list):
        thumbnails = []
    urls = [info.get("thumbnail"), *[t.get("url") for t in reversed(thumbnails) if isinstance(t, dict)]]
    sources = list(dict.fromkeys(url for url in urls if isinstance(url, str) and url))[:3]
    for index, url in enumerate(sources):
        try:
            raw = directory / "artwork-input"
            raw.write_bytes(fetch(url))
            probe = json.loads(run_command(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                                           "-show_entries", "stream=codec_type,width,height", "-of", "json", str(raw)], timeout=10))
            streams = probe.get("streams", [])
            if len(streams) != 1 or streams[0].get("codec_type") != "video":
                raise ValueError("Artwork is not a single image")
            width, height = int(streams[0].get("width", 0)), int(streams[0].get("height", 0))
            if not 0 < width * height <= 25_000_000:
                raise ValueError("Artwork dimensions exceed limits")
            output = directory / "cover.jpg"
            run_command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-protocol_whitelist", "file,pipe",
                         "-i", str(raw), "-frames:v", "1", "-vf", "scale='min(1000,iw)':'min(1000,ih)':force_original_aspect_ratio=decrease",
                         "-threads", "1", str(output)], timeout=20, log=log)
            log.write("Artwork selected: source.\n")
            return output
        except Exception as exc:
            log.write(f"Artwork candidate {index + 1} skipped: {type(exc).__name__}.\n")
    log.write("No reliable artwork available; keeping audio without embedded artwork.\n")
    return None
