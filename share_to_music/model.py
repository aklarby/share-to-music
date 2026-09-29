"""Optional native Shortcuts enrichment, enabled only after an interactive setup test."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
import re
import tempfile

from .metadata import model_tags

SHORTCUT = "Clean Music Tags"
MODEL_TIMEOUT = 45
MAX_OUTPUT = 8192
READY_FILE = "ai-ready.json"
SETUP_SAMPLE = {"title": "Example Artist - Example Song (Official Audio).mp3",
                "artist": "Example Artist", "track": "Example Song", "duration": 180}


def source_context(info):
    # Never send source URLs, descriptions, cookies, paths, or private-track tokens.
    result = {}
    for field in ("title", "track", "artist", "uploader", "album"):
        value = info.get(field)
        if isinstance(value, str):
            result[field] = " ".join(value.split())[:300]
    duration = info.get("duration")
    if isinstance(duration, (int, float)) and 0 < duration <= 7200:
        result["duration"] = duration
    return result


def ready(root):
    try:
        return json.loads((root / READY_FILE).read_text()) == {"shortcut": SHORTCUT, "version": 1}
    except (OSError, ValueError):
        return False


def disable(root):
    (root / READY_FILE).unlink(missing_ok=True)


def run_model(info, directory, log, run_command):
    """Execute the native shortcut with data files and a fixed, bounded command."""
    with tempfile.TemporaryDirectory(prefix="model-", dir=directory) as temp:
        source = Path(temp) / "source.json"
        output = Path(temp) / "response.json"
        source.write_text(json.dumps(source_context(info), ensure_ascii=False))
        run_command(["/usr/bin/shortcuts", "run", SHORTCUT,
                     "--input-path", str(source), "--output-path", str(output),
                     "--output-type", "public.plain-text"], timeout=MODEL_TIMEOUT, log=log)
        with output.open("rb") as handle:
            data = handle.read(MAX_OUTPUT + 1)
        if len(data) > MAX_OUTPUT:
            raise ValueError("Model output exceeds 8 KB")
        text = data.decode("utf-8-sig").strip()
        # Text output avoids macOS ChatGPT Dictionary-mode errors. Accept a JSON code fence too.
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
        value = json.loads(text)
        if not isinstance(value, dict) or not all(key in value for key in ("title", "artist")):
            raise ValueError("Model output must be a JSON dictionary with title and artist")
        for key in ("title", "artist"):
            item = value[key]
            if item is not None and (not isinstance(item, str) or len(item) > 300
                                     or any(ord(c) < 32 for c in item)):
                raise ValueError("Model title/artist must be short text or null")
        return value


def setup(root, log, run_command):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    disable(root)
    result = run_model(SETUP_SAMPLE, root, log, run_command)
    tags = model_tags(result)
    if tags.get("title") != "Example Song" or tags.get("artist") != "Example Artist":
        raise ValueError("The setup sample was not returned correctly. Check the helper's prompt/input/output.")
    marker = root / READY_FILE
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps({"shortcut": SHORTCUT, "version": 1}))
    temporary.replace(marker)
    return tags


def suggest(root, info, directory, log, run_command):
    if not ready(root):
        log.write("AI skipped: run setup-ai on this Mac to complete first-run permissions.\n")
        return None
    try:
        value = run_model(info, directory, log, run_command)
        log.write("AI returned song tags.\n")
        return value
    except Exception as exc:
        # Do not prompt/retry a broken model on every unattended job.
        with contextlib.suppress(OSError):
            disable(root)
        log.write(f"AI unavailable ({type(exc).__name__}); using source tags. Run setup-ai to re-enable.\n")
        return None
