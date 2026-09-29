"""Exercise real ffmpeg/ffprobe locally; never download or modify a Music library."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from share_to_music import core, model


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe are not installed")
class ConversionTests(unittest.TestCase):
    def enriched_audio(self, root, *, embed_failure=False, model_failure=False, artwork_failure=False):
        cover = root / "fixture.jpg"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=blue:s=64x64", "-frames:v", "1", "-threads", "1", str(cover)], check=True)
        info = {"extractor_key": "Youtube", "id": "BaW_jenozKc", "title": "Artist - Song (Unreleased).mp3",
                "uploader": "Fan upload", "duration": 1, "album": "Source Album",
                "thumbnail": "https://i.ytimg.com/vi/test.jpg"}
        original = core.run_command
        before = []

        def packets(path):
            return json.loads(original(["ffprobe", "-v", "error", "-select_streams", "a", "-show_packets",
                                        "-show_data_hash", "sha256", "-of", "json", str(path)], timeout=10))["packets"]

        def fake_download(args, **kwargs):
            if args[0] == "/usr/bin/shortcuts":
                if model_failure:
                    raise core.UserError("Model permission denied")
                output = Path(args[args.index("--output-path") + 1])
                output.write_text(json.dumps({"title": "Clean Song", "artist": "Real Artist"}))
                return ""
            if args[0] == "yt-dlp":
                staging = root / "staging/testjob"
                source = staging / "source.wav"
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                "sine=frequency=440:duration=1", str(source)], check=True)
                Path(args[args.index("--print-to-file") + 2]).write_text(json.dumps({**info, "filepath": str(source)}) + "\n")
                return ""
            if args[0] == "ffmpeg" and "-disposition:v" in args:
                if embed_failure:
                    raise core.UserError("Artwork mux failed")
            result = original(args, **kwargs)
            if args[0] == "ffmpeg" and args[-1].endswith(".partial.m4a"):
                before.extend(packet["data_hash"] for packet in packets(args[-1]))
            return result

        def fetch(url, **kwargs):
            if artwork_failure:
                raise OSError('Source artwork unavailable')
            return cover.read_bytes()

        (root / model.READY_FILE).write_text(json.dumps({"shortcut": model.SHORTCUT, "version": 1}))
        with (root / "test.log").open("w") as log, \
                patch("share_to_music.metadata.fetch", side_effect=fetch), \
                patch("share_to_music.core.run_command", side_effect=fake_download):
            audio = core.download_audio(root, {"id": "testjob"}, info, "unused", log)
        probe = json.loads(original(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(audio)], timeout=10))
        self.assertEqual([packet["data_hash"] for packet in packets(audio)], before)
        self.assertEqual(probe["format"]["tags"]["comment"], "share-to-music:youtube:BaW_jenozKc")
        self.assertEqual(probe["format"]["tags"]["album"], "SoundCloud")
        self.assertEqual(probe["format"]["tags"]["album_artist"], "Various Artists")
        self.assertEqual(probe["format"]["tags"]["compilation"], "1")
        return audio, probe

    def test_real_artwork_and_model_tags_are_embedded_without_reencoding_aac(self):
        with tempfile.TemporaryDirectory() as temp:
            _, probe = self.enriched_audio(Path(temp))
        self.assertEqual(probe["format"]["tags"]["title"], "Clean Song")
        self.assertEqual(probe["format"]["tags"]["artist"], "Real Artist")
        self.assertTrue(any(s.get("disposition", {}).get("attached_pic") == 1 for s in probe["streams"]))

    def test_source_artwork_failure_preserves_valid_audio_and_album_grouping(self):
        with tempfile.TemporaryDirectory() as temp:
            _, probe = self.enriched_audio(Path(temp), artwork_failure=True)
        self.assertEqual(probe["format"]["tags"]["artist"], "Real Artist")
        self.assertFalse(any(s.get("disposition", {}).get("attached_pic") == 1 for s in probe["streams"]))

    def test_embedding_failure_preserves_valid_tagged_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            _, probe = self.enriched_audio(Path(temp), embed_failure=True)
        self.assertEqual(probe["format"]["tags"]["title"], "Clean Song")
        self.assertFalse(any(s.get("disposition", {}).get("attached_pic") == 1 for s in probe["streams"]))

    def test_model_failure_preserves_audio_artwork_and_source_tags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio, probe = self.enriched_audio(root, model_failure=True)
            self.assertTrue(audio.exists())
            self.assertFalse(model.ready(root))
        self.assertEqual(probe["format"]["tags"]["title"], "Artist - Song")
        self.assertEqual(probe["format"]["tags"]["artist"], "Fan upload")
        self.assertTrue(any(s.get("disposition", {}).get("attached_pic") == 1 for s in probe["streams"]))

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

            with (root / "test.log").open("w") as log, patch("share_to_music.core.find_artwork", return_value=None), patch("share_to_music.core.run_command", side_effect=fake_download):
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
