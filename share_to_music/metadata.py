"""Conservative tag cleanup and bounded artwork retrieval from known image CDNs."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_IMAGE = 5_000_000
MAX_JSON = 1_000_000
VARIANTS = ("unreleased", "live", "remix", "cover", "instrumental", "sped up", "slowed", "reverb",
            "acoustic", "demo", "edit", "mix", "version", "nightcore", "extended", "remaster", "remastered")
IMAGE_HOSTS = ("mzstatic.com", "sndcdn.com", "ytimg.com")


def clean_text(value, limit=300):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 and not c.isspace() for c in value):
        return ""
    return " ".join(value.split()).strip()


def clean_title(value):
    value = clean_text(value)
    value = re.sub(r"\.(?:mp3|m4a|wav|flac|aac|mp4|webm)$", "", value, flags=re.I).strip()
    # Display names omit upload/recording labels; the original metadata remains
    # available separately for conservative artwork matching.
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


def source_versions(info):
    return versions(str(info.get("title") or "")) | versions(str(info.get("track") or ""))


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
    return {"title": title, "artist": artist,
            "album": clean_text(info.get("album")) or "Shared Audio"}


def allowed_url(url, kind):
    if not isinstance(url, str) or len(url) > 4096:
        raise ValueError("Invalid artwork URL")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Artwork requires HTTPS without credentials or a custom port")
    valid = host == "itunes.apple.com" if kind == "catalog" else any(
        host == domain or host.endswith("." + domain) for domain in IMAGE_HOSTS)
    if not valid:
        raise ValueError("Artwork host is not allowed")
    return url


class SafeRedirects(HTTPRedirectHandler):
    max_redirections = 3

    def __init__(self, kind):
        self.kind = kind

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl, self.kind)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, *, kind, limit):
    allowed_url(url, kind)
    request = Request(url, headers={"User-Agent": "ShareToMusic/0.2", "Accept": "application/json" if kind == "catalog" else "image/*"})
    deadline = time.monotonic() + 10
    with build_opener(SafeRedirects(kind)).open(request, timeout=5) as response:
        allowed_url(response.url, kind)
        content_type = response.headers.get_content_type()
        if kind == "image" and content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Unsupported artwork content type")
        chunks, size = [], 0
        while size <= limit:
            if time.monotonic() > deadline:
                raise TimeoutError("Artwork response timed out")
            chunk = response.read1(min(65536, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        data = b"".join(chunks)
        if not data or len(data) > limit:
            raise ValueError("Artwork response is empty or too large")
        return data


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


def catalog_match(tags, duration, results):
    if (versions(tags["title"]) or not normalized(tags["title"]) or not normalized(tags["artist"])
            or not math.isfinite(duration) or duration <= 0 or not isinstance(results, list)):
        return None
    matches = []
    for item in results:
        if not isinstance(item, dict) or item.get("kind") != "song":
            continue
        if versions(str(item.get("trackName") or "")):
            continue
        if normalized(clean_title(item.get("trackName"))) != normalized(tags["title"]):
            continue
        if normalized(clean_text(item.get("artistName"))) != normalized(tags["artist"]):
            continue
        millis = item.get("trackTimeMillis")
        if (isinstance(millis, bool) or not isinstance(millis, (int, float)) or not math.isfinite(millis)
                or abs(millis / 1000 - duration) > max(5, duration * .03)):
            continue
        if item.get("artworkUrl100"):
            matches.append(item)
    # Different matching album releases can have different artwork. Don't guess.
    albums = {(normalized(clean_text(item.get("collectionName"))), item.get("collectionId"),
               item.get("artworkUrl100")) for item in matches}
    return matches[0] if matches and len(albums) == 1 else None


def find_artwork(tags, info, directory: Path, log, run_command):
    """Optional enrichment: a lookup or image failure never fails the audio job."""
    candidates = []
    if not source_versions(info) and not versions(tags["title"]) and tags["artist"] != "Unknown artist":
        try:
            query = urlencode({"term": tags["artist"] + " " + tags["title"], "entity": "song", "media": "music", "limit": 10})
            result = json.loads(fetch("https://itunes.apple.com/search?" + query, kind="catalog", limit=MAX_JSON))
            match = catalog_match(tags, float(info["duration"]), result.get("results", []))
            if match:
                url = match["artworkUrl100"]
                # The CDN accepts a requested image size; source URL remains fallback.
                larger = re.sub(r"/100x100[^/]*\.(jpg|png)$", r"/600x600bb.\1", url)
                candidates.append((larger, "catalog", clean_text(match.get("collectionName"))))
                if larger != url:
                    candidates.append((url, "catalog", clean_text(match.get("collectionName"))))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            log.write(f"Artwork catalog unavailable: {type(exc).__name__}; trying source image.\n")
    thumbnails = info.get("thumbnails") or []
    if not isinstance(thumbnails, list):
        thumbnails = []
    source_urls = [info.get("thumbnail"), *[t.get("url") for t in reversed(thumbnails) if isinstance(t, dict)]]
    for url in source_urls:
        if isinstance(url, str) and url and url not in [c[0] for c in candidates]:
            candidates.append((url, "source", ""))
    for index, (url, origin, album) in enumerate(candidates[:5]):
        try:
            raw = directory / "artwork-input"
            raw.write_bytes(fetch(url, kind="image", limit=MAX_IMAGE))
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
            log.write(f"Artwork selected: {origin}.\n")
            return output, album
        except Exception as exc:
            log.write(f"Artwork candidate {index + 1} skipped: {type(exc).__name__}.\n")
    log.write("No reliable artwork available; keeping audio without embedded artwork.\n")
    return None, ""
