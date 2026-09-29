#!/usr/bin/env python3
"""Install a per-user command and launchd agent. Never changes SSH or Music settings."""

import argparse
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys

LABEL = "com.share-to-music.worker"
REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true", help="Remove worker/command; preserve audio and queue")
    parser.add_argument("--prefix", type=Path, default=Path.home() / "Library/Application Support/Share to Music")
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local/bin")
    parser.add_argument("--agent-dir", type=Path, default=Path.home() / "Library/LaunchAgents")
    parser.add_argument("--no-launch", action="store_true", help="Write files without loading launchd (for testing)")
    args = parser.parse_args()
    if sys.version_info < (3, 10) or (sys.platform != "darwin" and not args.no_launch):
        parser.error("Installation requires macOS and Python 3.10+.")
    os.umask(0o077)
    prefix, bin_dir, agent_dir = args.prefix.expanduser().absolute(), args.bin_dir.expanduser().absolute(), args.agent_dir.expanduser().absolute()
    agent = agent_dir / (LABEL + ".plist")
    command = bin_dir / "share-to-music"
    app = prefix / "app"
    domain = f"gui/{os.getuid()}"
    if not args.uninstall and not args.no_launch:
        missing = [name for name in ("yt-dlp", "ffmpeg", "ffprobe", "deno") if not shutil.which(name)]
        if missing:
            parser.error("Missing " + ", ".join(missing) + ". Run: brew install python yt-dlp ffmpeg deno")
    if command.exists() and "# Installed by Share to Music" not in command.read_text():
        parser.error(f"Refusing to replace an unrelated command: {command}")
    if not args.no_launch:
        loaded = subprocess.run(["/bin/launchctl", "print", f"{domain}/{LABEL}"], capture_output=True)
        if loaded.returncode == 0:
            subprocess.run(["/bin/launchctl", "bootout", f"{domain}/{LABEL}"], check=True)
    if args.uninstall:
        command.unlink(missing_ok=True)
        agent.unlink(missing_ok=True)
        print(f"Worker and command removed. Audio, queue, and application files remain in {prefix}.")
        print("Music library entries are unchanged.")
        return
    for directory in (app, bin_dir, agent_dir, prefix / "logs"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copytree(REPO / "share_to_music", app / "share_to_music", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    python = shutil.which("python3") or sys.executable
    # launchd and SSH do not inherit the interactive shell's Homebrew PATH.
    search_path = ":".join(dict.fromkeys([str(Path(python).parent), "/opt/homebrew/bin", "/usr/local/bin",
                                        "/usr/bin", "/bin", "/usr/sbin", "/sbin"]))
    wrapper = "\n".join(["#!/bin/sh", "# Installed by Share to Music", "set -eu",
                         f"export PATH={shlex.quote(search_path)}",
                         f"export PYTHONPATH={shlex.quote(str(app))}",
                         f"exec {shlex.quote(python)} -m share_to_music --data-dir {shlex.quote(str(prefix))} \"$@\"", ""])
    command.write_text(wrapper)
    command.chmod(0o700)
    config = {
        "Label": LABEL, "ProgramArguments": [str(command), "worker"],
        "RunAtLoad": True, "StartInterval": 15, "ProcessType": "Background",
        "EnvironmentVariables": {"PATH": search_path},
        "StandardOutPath": str(prefix / "logs/worker.log"),
        "StandardErrorPath": str(prefix / "logs/worker-error.log"),
        "Umask": 0o077,
    }
    with agent.open("wb") as handle:
        plistlib.dump(config, handle)
    if not args.no_launch:
        subprocess.run(["/bin/launchctl", "bootstrap", domain, str(agent)], check=True)
    print(f"Installed: {command}")
    print(f"Private data: {prefix}")
    print("Worker checks the queue every 15 seconds while you are logged in and the Mac is awake.")
    print('Next: "$HOME/.local/bin/share-to-music" doctor --music')
    print('For optional AI: import Clean Music Tags.shortcut on this Mac, then run "$HOME/.local/bin/share-to-music" setup-ai')


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Installation failed: {exc}")
