import base64
import contextlib
import fcntl
import io
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

from share_to_music import core
from share_to_music.__main__ import main
from scripts.build_shortcut import build

URL = "https://www.youtube.com/watch?v=BaW_jenozKc"
INFO = {"extractor_key": "Youtube", "id": "BaW_jenozKc", "title": "A test track", "duration": 10}


class URLTests(unittest.TestCase):
    def test_youtube_variants_deduplicate(self):
        for value in [URL + "&list=example", "https://youtu.be/BaW_jenozKc?si=abc",
                      "https://m.youtube.com/shorts/BaW_jenozKc", "https://music.youtube.com/watch?v=BaW_jenozKc"]:
            with self.subTest(value=value):
                self.assertEqual(core.normalize_url(value), URL)

    def test_soundcloud_tracking_and_private_tokens(self):
        self.assertEqual(core.normalize_url("https://m.soundcloud.com/artist/track?utm_source=share"),
                         "https://soundcloud.com/artist/track")
        self.assertEqual(core.normalize_url("https://soundcloud.com/artist/track/s-abc?secret_token=s-xyz&utm=a"),
                         "https://soundcloud.com/artist/track/s-abc?secret_token=s-xyz")
        self.assertEqual(core.normalize_url("https://on.soundcloud.com/abc123?si=x"), "https://on.soundcloud.com/abc123")

    def test_reject_untrusted_and_collection_urls(self):
        for value in ["file:///etc/passwd", "http://soundcloud.com/a/b", "https://youtube.com.evil.test/watch?v=BaW_jenozKc",
                      "https://user@youtube.com/watch?v=BaW_jenozKc", "https://soundcloud.com:222/a/b",
                      "https://soundcloud.com/a/sets/b", "https://soundcloud.com/a", "https://youtube.com/playlist?list=a",
                      "https://soundcloud.com/a/b\nhttps://soundcloud.com/c/d", "--exec=bad", "https://soundcloud.com/a/$(touch)",
                      "https://127.0.0.1/a/b", "https://soundcloud.com/a/%2e%2e"]:
            with self.subTest(value=value), self.assertRaises(core.UserError):
                core.normalize_url(value)

    def test_base64_decode_and_validate(self):
        self.assertEqual(core.decode_url(base64.b64encode(URL.encode()).decode()), URL)
        for value in ["!invalid!", "/w==", "a" * 20000]:
            with self.assertRaises(core.UserError):
                core.decode_url(value)

    def test_redirect_rejects_external_and_local_targets_before_request(self):
        for target in ["http://127.0.0.1", "https://example.com/track", URL]:
            with self.assertRaises(core.UserError):
                core.SoundCloudRedirects().redirect_request(Request("https://on.soundcloud.com/abc"), None, 302,
                                                           "Found", {}, target)

    @patch("share_to_music.core.run_command")
    def test_reject_live_playlist_and_oversize(self, run):
        for extra in [{"is_live": True}, {"_type": "playlist", "entries": []}, {"duration": 99999},
                      {"duration": None}, {"extractor_key": "Generic"}]:
            run.return_value = json.dumps({**INFO, **extra})
            with self.assertRaises(core.UserError):
                core.inspect_media(URL)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = core.connect(self.root)
        self.addCleanup(self.db.close)
        self.audio = self.root / "test.m4a"
        self.audio.write_bytes(b"test audio fixture")

    def job(self, job_id):
        return self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    def test_duplicate_submission_is_one_job(self):
        first = core.enqueue(self.db, URL)
        second = core.enqueue(self.db, "https://youtu.be/BaW_jenozKc?si=foo")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)

    @patch("share_to_music.core.import_music", return_value="0123456789ABCDEF")
    @patch("share_to_music.core.download_audio")
    @patch("share_to_music.core.inspect_media", return_value=INFO)
    def test_success_is_recorded_only_after_import(self, inspect, download, importer):
        download.return_value = self.audio
        job = core.enqueue(self.db, URL)
        core.process_queue(self.root)
        self.assertEqual(self.job(job["id"])["state"], "complete")
        importer.assert_called_once_with(self.audio, "youtube:BaW_jenozKc")
        core.process_queue(self.root)
        self.assertEqual(importer.call_count, 1)

    @patch("share_to_music.core.import_music", side_effect=[core.UserError("Automation denied"), "0123456789ABCDEF"])
    @patch("share_to_music.core.download_audio")
    @patch("share_to_music.core.inspect_media", return_value=INFO)
    def test_failed_import_retries_without_redownload(self, inspect, download, importer):
        download.return_value = self.audio
        job = core.enqueue(self.db, URL)
        core.process_queue(self.root)
        self.assertEqual(self.job(job["id"])["state"], "failed")
        self.assertIn("Automation denied", self.job(job["id"])["error"])
        core.retry(self.db, job["id"])
        core.process_queue(self.root)
        self.assertEqual(self.job(job["id"])["state"], "complete")
        self.assertEqual(download.call_count, 1)
        self.assertEqual(self.job(job["id"])["attempts"], 2)

    @patch("share_to_music.core.import_music", return_value="0123456789ABCDEF")
    def test_abandoned_import_recovers_on_next_worker(self, importer):
        job = core.enqueue(self.db, URL)
        core.update(self.db, job["id"], state="importing", media_key="youtube:BaW_jenozKc", audio_path=str(self.audio))
        core.process_queue(self.root)
        self.assertEqual(self.job(job["id"])["state"], "complete")

    @patch("share_to_music.core.inspect_media", side_effect=core.UserError("Network unavailable"))
    @patch("share_to_music.core.import_music")
    def test_download_failure_never_imports_or_reports_success(self, importer, inspect):
        job = core.enqueue(self.db, URL)
        core.process_queue(self.root)
        self.assertEqual(self.job(job["id"])["state"], "failed")
        self.assertIsNone(self.job(job["id"])["music_id"])
        importer.assert_not_called()

    def test_worker_lock_prevents_two_workers(self):
        job = core.enqueue(self.db, URL)
        with (self.root / "worker.lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            self.assertEqual(core.process_queue(self.root), 0)
        self.assertEqual(self.job(job["id"])["state"], "queued")

    def test_retry_rejects_unknown_and_completed_jobs(self):
        job = core.enqueue(self.db, URL)
        for job_id in ["unknown", job["id"]]:
            with self.assertRaises(core.UserError):
                core.retry(self.db, job_id)

    def test_cli_base64_roundtrip_and_json_status(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(["--data-dir", str(self.root), "enqueue", "--base64",
                                   base64.b64encode(URL.encode()).decode()]), 0)
        self.assertIn("Queued on Mac", stdout.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(["--data-dir", str(self.root), "status", "--json"]), 0)
        self.assertEqual(json.loads(stdout.getvalue())[0]["url"], URL)

    def test_cli_plain_stdin_roundtrip_and_duplicate(self):
        command = [sys.executable, "-m", "share_to_music", "--data-dir", str(self.root), "enqueue", "--stdin"]
        first = subprocess.run(command, input=URL + "\n", text=True, capture_output=True, timeout=5)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = subprocess.run(command, input=URL, text=True, capture_output=True, timeout=5)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(self.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT url FROM jobs").fetchone()[0], URL)

    def test_cli_plain_stdin_rejects_empty_oversize_and_multiple_links(self):
        command = [sys.executable, "-m", "share_to_music", "--data-dir", str(self.root), "enqueue", "--stdin"]
        for value in ["", " " * (core.MAX_INPUT + 1), URL + "\n" + URL, "$(touch /tmp/not-a-url)"]:
            with self.subTest(value=value[:40]):
                result = subprocess.run(command, input=value, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("Error:", result.stderr)
        self.assertEqual(self.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 0)


class PackagingTests(unittest.TestCase):
    def test_direct_run_requests_text_instead_of_empty_share_input(self):
        data = build()
        self.assertEqual(data["WFWorkflowNoInputBehavior"], {
            "Name": "WFWorkflowNoInputBehaviorAskForInput",
            "Parameters": {"ItemClass": "WFStringContentItem"},
        })
        self.assertTrue(data["WFWorkflowHasShortcutInputVariables"])

    def test_tailscale_connect_and_exit_node_precede_ssh(self):
        actions = build()["WFWorkflowActions"]
        self.assertEqual([a["WFWorkflowActionIdentifier"] for a in actions[:2]],
                         ["io.tailscale.ipn.ios.ConnectIntent", "io.tailscale.ipn.ios.UseExitNodeIntent"])
        for action in actions[:2]:
            descriptor = action["WFWorkflowActionParameters"]["AppIntentDescriptor"]
            self.assertEqual(descriptor["BundleIdentifier"], "io.tailscale.ipn.ios")
        self.assertNotIn("exitNode", actions[1]["WFWorkflowActionParameters"])
        ssh = next(a["WFWorkflowActionParameters"] for a in actions if a["WFWorkflowActionIdentifier"].endswith("runsshscript"))
        self.assertTrue(ssh["WFSSHHost"].endswith(".ts.net"))

    def test_shortcut_passes_url_as_text_stdin_without_shell_interpolation(self):
        data = build()
        actions = data["WFWorkflowActions"]
        self.assertFalse(any(x["WFWorkflowActionIdentifier"].endswith("base64encode") for x in actions))
        first = next(x["WFWorkflowActionParameters"] for x in actions if x["WFWorkflowActionIdentifier"].endswith("getitemfromlist"))
        ssh = next(x["WFWorkflowActionParameters"] for x in actions if x["WFWorkflowActionIdentifier"].endswith("runsshscript"))
        self.assertEqual(ssh["WFSSHScript"], '"$HOME/.local/bin/share-to-music" enqueue --stdin\n')
        self.assertEqual(ssh["WFInput"]["Value"]["OutputUUID"], first["UUID"])
        self.assertEqual(ssh["WFInput"]["Value"]["Aggrandizements"][0]["CoercionItemClass"], "WFStringContentItem")
        self.assertNotIn("WFSSHPassword", ssh)
        self.assertIn("ActionExtension", data["WFWorkflowTypes"])

    def test_shortcut_text_fields_use_string_tokens(self):
        actions = build()["WFWorkflowActions"]
        urls = next(x["WFWorkflowActionParameters"] for x in actions if x["WFWorkflowActionIdentifier"].endswith("detect.link"))
        result = next(x["WFWorkflowActionParameters"] for x in actions if x["WFWorkflowActionIdentifier"].endswith("showresult"))
        for value in [urls["WFInput"], result["Text"]]:
            self.assertEqual(value["WFSerializationType"], "WFTextTokenString")
            self.assertIn("{0, 1}", value["Value"]["attachmentsByRange"])

    def test_install_and_uninstall_preserve_audio(self):
        with tempfile.TemporaryDirectory(prefix="Share Music test ' ") as temp:
            root = Path(temp)
            prefix = root / "Application Support"
            options = [sys.executable, "scripts/install.py", "--prefix", str(prefix), "--bin-dir", str(root / "bin"),
                       "--agent-dir", str(root / "agents"), "--no-launch"]
            subprocess.run(options, check=True, capture_output=True)
            command = root / "bin/share-to-music"
            result = subprocess.run([str(command), "--version"], check=True, capture_output=True, text=True)
            self.assertIn("0.2.0", result.stdout)
            agent = plistlib.loads((root / "agents/com.share-to-music.worker.plist").read_bytes())
            self.assertEqual(agent["ProgramArguments"], [str(command), "worker"])
            self.assertEqual(agent["StartInterval"], 15)
            audio = prefix / "audio/keep.m4a"
            audio.parent.mkdir()
            audio.write_bytes(b"keep")
            subprocess.run(options + ["--uninstall"], check=True, capture_output=True)
            self.assertTrue(audio.exists())
            self.assertFalse(command.exists())


if __name__ == "__main__":
    unittest.main()
