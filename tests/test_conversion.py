"""Exercise real ffmpeg/ffprobe locally; never download or modify a Music library."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from share_to_music import core


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe are not installed")
class ConversionTests(unittest.TestCase):
    def test_real_aac_conversion_tags_and_cache(self):
        with tempfile.TemporaryDirectory(prefix="audio test '") as temp:
            root = Path(temp)
            info = {"extractor_key": "Youtube", "id": "BaW_jenozKc", "title": "Quotes ' \" & café",
                    "uploader": "A test artist", "duration": 1}
            job = {"id": "testjob"}
            original = core.run_command

            def fake_download(args, **kwargs):
                if args[0] != "yt-dlp":
                    return original(args, **kwargs)
                staging = root / "staging/testjob"
                source = staging / "source.wav"
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                "sine=frequency=440:duration=1", str(source)], check=True)
                manifest = Path(args[args.index("--print-to-file") + 2])
                manifest.write_text(json.dumps({**info, "filepath": str(source)}) + "\n")
                return ""

            with (root / "test.log").open("w") as log, patch("share_to_music.core.run_command", side_effect=fake_download):
                audio = core.download_audio(root, job, info, "https://www.youtube.com/watch?v=BaW_jenozKc", log)
                cached = core.download_audio(root, job, info, "unused", log)
            self.assertEqual(audio, cached)
            probe = json.loads(original(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(audio)], timeout=20))
            self.assertEqual(probe["streams"][0]["codec_name"], "aac")
            self.assertEqual(probe["format"]["tags"]["title"], info["title"])
            self.assertEqual(probe["format"]["tags"]["comment"], "share-to-music:youtube:BaW_jenozKc")
            self.assertFalse((root / "staging/testjob").exists())


if __name__ == "__main__":
    unittest.main()
