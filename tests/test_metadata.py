import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

from share_to_music import core, metadata, model
from share_to_music.__main__ import main
from scripts.build_metadata_shortcut import build


class MetadataTests(unittest.TestCase):
    def test_user_examples_accept_real_model_results_unchanged(self):
        examples = json.loads((Path(__file__).parent / 'fixtures/metadata-examples.json').read_text())
        for example in examples:
            selected = metadata.choose_tags({'title': example['source_title']}, example['output'])
            self.assertEqual(selected['title'], example['output']['title'])
            self.assertEqual(selected['artist'], example['output']['artist'])
            self.assertIn(' & ', selected['artist'])
            self.assertNotIn('Unreleased', selected['title'])
            self.assertNotIn('.mp3', selected['title'])

    def test_clean_display_titles_remove_version_and_promotion_labels(self):
        for original in ['Song (Official Audio).mp3', 'Song (Unreleased)', 'Song (Someone Remix)',
                         'Song (Live at Wembley)', 'Song - Acoustic']:
            self.assertEqual(metadata.clean_title(original), 'Song')
        self.assertEqual(metadata.clean_title('Live Forever'), 'Live Forever')
        self.assertEqual(metadata.versions('Delivery'), set())
        self.assertEqual(metadata.clean_title('東京 (Live)'), '東京')

    def test_model_names_are_used_directly_without_confidence_or_source_gate(self):
        info = {'title': 'Poorly named upload (Unreleased).mp3', 'uploader': 'Fan channel'}
        self.assertEqual(metadata.choose_tags(info, {'title': 'Actual Song', 'artist': 'Actual Artist'}),
                         {'title': 'Actual Song', 'artist': 'Actual Artist', 'album': 'SoundCloud',
                          'album_artist': 'Various Artists', 'compilation': '1'})
        # The caller trusts model names, even when its wording differs from the source.
        self.assertEqual(metadata.choose_tags(info, {'title': 'Song (Live)', 'artist': 'Artist'})['title'], 'Song (Live)')

    def test_missing_model_fields_fall_back_individually(self):
        info = {'title': 'Song.mp3', 'uploader': 'Source', 'album': 'Source Album'}
        for value in [None, [], 'invalid JSON', {'title': None, 'artist': None},
                      {'title': 'Bad\x00', 'artist': None}, {'title': 'a' * 301}]:
            self.assertEqual(metadata.choose_tags(info, value)['title'], 'Song')
        self.assertEqual(metadata.choose_tags(info, {'title': 'Clean', 'artist': None, 'album': 'Invented'}),
                         {'title': 'Clean', 'artist': 'Source', 'album': 'SoundCloud',
                          'album_artist': 'Various Artists', 'compilation': '1'})

    def test_artwork_hosts_and_redirects_are_restricted(self):
        for value in ['http://i.scdn.co/a', 'https://127.0.0.1/a', 'https://i.ytimg.com.evil.test/a',
                      'https://user@i.ytimg.com/a', 'https://i.ytimg.com:8443/a', 'file:///etc/passwd',
                      'https://itunes.apple.com/search', 'https://a.mzstatic.com/cover.jpg']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                metadata.allowed_url(value)
        with self.assertRaises(ValueError):
            metadata.SafeRedirects().redirect_request(Request('https://i.ytimg.com/a'), None,
                                                             302, 'Found', {}, 'https://evil.test/a')
        self.assertEqual(metadata.allowed_url('https://i.ytimg.com/vi/a.jpg'), 'https://i.ytimg.com/vi/a.jpg')

    @patch('share_to_music.metadata.fetch', side_effect=OSError('offline'))
    def test_artwork_failure_is_optional(self, fetch):
        with tempfile.TemporaryDirectory() as temp:
            result = metadata.find_artwork({'duration': 200, 'thumbnail': 'https://i.ytimg.com/vi/a.jpg'},
                Path(temp), io.StringIO(), lambda *a, **k: '')
        self.assertIsNone(result)

    def test_source_thumbnail_failure_tries_another_size(self):
        def fetch(url, **kwargs):
            if url.endswith('large.jpg'):
                raise OSError('source image size unavailable')
            return b'image fixture'
        def run(args, **kwargs):
            if args[0] == 'ffprobe':
                return json.dumps({'streams': [{'codec_type': 'video', 'width': 64, 'height': 64}]})
            Path(args[-1]).write_bytes(b'normalized jpeg')
        with tempfile.TemporaryDirectory() as temp, patch('share_to_music.metadata.fetch', side_effect=fetch) as requests:
            cover = metadata.find_artwork({'thumbnail': 'https://i1.sndcdn.com/large.jpg',
                'thumbnails': [{'url': 'https://i1.sndcdn.com/small.jpg'}, {'url': 'https://i1.sndcdn.com/large.jpg'}]},
                Path(temp), io.StringIO(), run)
            self.assertTrue(cover.exists())
            self.assertEqual([call.args[0] for call in requests.call_args_list],
                             ['https://i1.sndcdn.com/large.jpg', 'https://i1.sndcdn.com/small.jpg'])

    def test_missing_thumbnail_makes_no_requests(self):
        with tempfile.TemporaryDirectory() as temp, patch('share_to_music.metadata.fetch') as fetch:
            metadata.find_artwork({'title': 'Song', 'track': 'Song', 'artist': 'Artist', 'duration': 200},
                Path(temp), io.StringIO(), lambda *a, **k: '')
            fetch.assert_not_called()

    def test_soundcloud_artwork_is_used_directly(self):
        def run(args, **kwargs):
            if args[0] == 'ffprobe':
                return json.dumps({'streams': [{'codec_type': 'video', 'width': 64, 'height': 64}]})
            Path(args[-1]).write_bytes(b'normalized jpeg')
        with tempfile.TemporaryDirectory() as temp, patch('share_to_music.metadata.fetch', return_value=b'source image') as fetch:
            cover = metadata.find_artwork({'extractor_key': 'Soundcloud', 'title': 'Song', 'duration': 200,
                 'thumbnail': 'https://i1.sndcdn.com/artwork.jpg'}, Path(temp), io.StringIO(), run)
            self.assertTrue(cover.exists())
            fetch.assert_called_once_with('https://i1.sndcdn.com/artwork.jpg')

    def test_source_image_failures_are_bounded_without_catalog_fallback(self):
        with tempfile.TemporaryDirectory() as temp, patch('share_to_music.metadata.fetch', side_effect=OSError('offline')) as requests:
            log = io.StringIO()
            cover = metadata.find_artwork({'extractor_key': 'Soundcloud', 'title': 'Song', 'duration': 200,
                 'thumbnails': [{'url': f'https://i1.sndcdn.com/{i}.jpg'} for i in range(10)]},
                Path(temp), log, lambda *a, **k: '')
            self.assertIsNone(cover)
            self.assertEqual([call.args[0] for call in requests.call_args_list],
                             [f'https://i1.sndcdn.com/{i}.jpg' for i in (9, 8, 7)])


class ModelTests(unittest.TestCase):
    def test_downloadable_helper_connects_input_to_model_and_returns_text(self):
        workflow = build()
        self.assertEqual(workflow['WFWorkflowName'], model.SHORTCUT)
        actions = workflow['WFWorkflowActions']
        self.assertEqual([a['WFWorkflowActionIdentifier'] for a in actions],
                         ['is.workflow.actions.gettext', 'is.workflow.actions.askllm', 'is.workflow.actions.gettext'])
        source, model_action, output = [a['WFWorkflowActionParameters'] for a in actions]
        source_token = next(iter(source['WFTextActionText']['Value']['attachmentsByRange'].values()))
        self.assertEqual(source_token['Type'], 'ExtensionInput')
        self.assertEqual(model_action['WFLLMModel'], 'ChatGPT')
        self.assertEqual(model_action['WFGenerativeResultType'], 'Text')
        prompt_token = next(iter(model_action['WFLLMPrompt']['Value']['attachmentsByRange'].values()))
        self.assertEqual(prompt_token['OutputUUID'], source['UUID'])
        result_token = next(iter(output['WFTextActionText']['Value']['attachmentsByRange'].values()))
        self.assertEqual(result_token['OutputUUID'], model_action['UUID'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = io.StringIO()

    def respond(self, value):
        def run(args, **kwargs):
            self.assertEqual(args[:3], ['/usr/bin/shortcuts', 'run', 'Clean Music Tags'])
            self.assertEqual(args[args.index('--output-type') + 1], 'public.plain-text')
            self.assertEqual(kwargs['timeout'], 45)
            source = Path(args[args.index('--input-path') + 1])
            self.assertLess(source.stat().st_size, 10000)
            self.assertNotIn('url', json.loads(source.read_text()))
            output = Path(args[args.index('--output-path') + 1])
            output.write_text(value if isinstance(value, str) else json.dumps(value))
        return run

    def enable(self):
        good = {'title': 'Example Song', 'artist': 'Example Artist'}
        model.setup(self.root, self.log, self.respond(good))

    def test_setup_roundtrip_enables_and_cleans_temporary_metadata(self):
        self.enable()
        self.assertTrue(model.ready(self.root))
        self.assertEqual([p.name for p in self.root.iterdir()], [model.READY_FILE])

    def test_fenced_json_from_text_output_is_accepted(self):
        value = model.run_model({}, self.root, self.log,
                                self.respond('```json\n{"title":"Song","artist":"Artist"}\n```'))
        self.assertEqual(value, {'title': 'Song', 'artist': 'Artist'})

    def test_model_is_never_called_before_setup(self):
        with patch('share_to_music.model.run_model') as run:
            self.assertIsNone(model.suggest(self.root, {}, self.root, self.log, run))
            run.assert_not_called()

    def test_source_payload_excludes_urls_private_tokens_and_descriptions(self):
        result = model.source_context({'title': 'x' * 1000, 'url': 'private', 'description': 'private',
                                       'cookies': 'private', 'artist': ['bad'], 'duration': float('nan')})
        self.assertEqual(result, {'title': 'x' * 300})

    def test_empty_names_keep_ai_enabled_for_next_song(self):
        self.enable()
        value = model.suggest(self.root, {}, self.root, self.log, self.respond({'title': None, 'artist': None}))
        self.assertEqual(value, {'title': None, 'artist': None})
        self.assertTrue(model.ready(self.root))

    def test_runtime_failure_disables_repeated_unattended_calls(self):
        for failure in [FileNotFoundError(), core.UserError('permission denied'), core.UserError('timed out')]:
            self.enable()
            with patch('share_to_music.model.run_model', side_effect=failure) as run:
                self.assertIsNone(model.suggest(self.root, {}, self.root, self.log, None))
                self.assertFalse(model.ready(self.root))
                model.suggest(self.root, {}, self.root, self.log, None)
                run.assert_called_once()

    def test_invalid_and_oversized_output_falls_back_and_disables(self):
        for value in ['not json', 'x' * 9000, [], {'unexpected': True},
                      {'title': '\x00', 'artist': 'A'}]:
            self.enable()
            self.assertIsNone(model.suggest(self.root, {}, self.root, self.log, self.respond(value)))
            self.assertFalse(model.ready(self.root))

    def test_setup_clears_previous_success_when_new_check_fails(self):
        self.enable()
        with self.assertRaises(ValueError):
            model.setup(self.root, self.log, self.respond({'title': 'Wrong', 'artist': 'Artist'}))
        self.assertFalse(model.ready(self.root))

    def test_enqueue_never_invokes_model(self):
        with patch('share_to_music.model.run_model') as run, contextlib.redirect_stdout(io.StringIO()), \
                patch('sys.stdin', io.StringIO('https://soundcloud.com/example/track')):
            self.assertEqual(main(['--data-dir', str(self.root), 'enqueue', '--stdin']), 0)
            run.assert_not_called()

    def test_real_process_timeout_is_bounded(self):
        import sys
        import time
        started = time.monotonic()
        with self.assertRaises(core.UserError):
            core.run_command([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=.1)
        self.assertLess(time.monotonic() - started, 3)


if __name__ == '__main__':
    unittest.main()
