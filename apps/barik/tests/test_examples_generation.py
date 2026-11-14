#!/usr/bin/env python3
"""Offline checks for content acceptance, API failures and saved generation progress."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import gen_examples as g

ROW = {'w': 'միջին խավ', 'hy': 'Տնտեսագետը ուսումնասիրում է միջին խավի եկամուտները։',
       'ru': 'Экономист изучает доходы среднего класса.',
       'en': 'The economist studies middle-class incomes.',
       'fr': 'L’économiste étudie les revenus des classes moyennes.',
       'es': 'El economista estudia los ingresos de la clase media.',
       'de': 'Der Ökonom untersucht die Einkommen der Mittelschicht.',
       'pt': 'O economista estuda a renda da classe média.'}


class Response:
    def __init__(self, status, payload, headers=None):
        self.status_code, self.payload = status, payload
        self.headers = headers or {}
        self.ok = 200 <= status < 300

    def json(self):
        return self.payload


def completion():
    compact = [[ROW[k] for k in ('w', 'hy', *g.LANGS)]]
    return Response(200, {'choices': [{'message': {'content': json.dumps({'examples': compact}, ensure_ascii=False)},
                                    'finish_reason': 'stop'}],
                          'usage': {'prompt_tokens': 20, 'completion_tokens': 30}})


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.config = g.provider_config('github', {'GITHUB_TOKEN': 'fixture-token-for-offline-tests'})
        self.part = [('միջին խավ', 'средний класс', 'middle class')]

    def test_compact_and_fenced_results_preserve_all_languages(self):
        raw = completion().json()['choices'][0]['message']['content']
        self.assertEqual(g.decode_examples('```json\n' + raw + '\n```'), [ROW])
        self.assertEqual(g.decode_examples('{"examples":[["incomplete"]]}'), [])

    def test_multiword_entry_requires_every_component_in_order(self):
        self.assertTrue(g.ok(ROW['w'], ROW))
        self.assertFalse(g.headword_in_sentence('միջին խավ', 'Խավի մասին միջին հոդվածը հետաքրքիր էր։'))

    def test_sensitive_headword_can_have_neutral_museum_context(self):
        row = dict(ROW, w='զինանոց', hy='Թանգարանում պահպանվել է հին զինանոցի ցուցանակը։')
        self.assertTrue(g.ok(row['w'], row))
        row['hy'] = 'Գրքում զինանոցի կողքին հիշատակվում են հարվածները։'
        self.assertFalse(g.ok(row['w'], row))

    def test_permanent_deployment_error_stops_without_retries(self):
        post = Mock(return_value=Response(404, {'error': {'code': 'DeploymentNotFound', 'message': 'Absent'}}))
        sleeper = Mock()
        with self.assertRaisesRegex(g.APIError, 'DeploymentNotFound'):
            g.request_examples(self.config, self.part, 'B2', post, sleeper)
        self.assertEqual(post.call_count, 1)
        sleeper.assert_not_called()

    def test_daily_quota_preserves_run_time_and_does_not_busy_retry(self):
        post = Mock(return_value=Response(429, {'error': {'code': 'RateLimit', 'message': 'Daily limit'}},
                                         {'Retry-After': '86400'}))
        sleeper = Mock()
        with self.assertRaises(g.QuotaError):
            g.request_examples(self.config, self.part, 'B2', post, sleeper)
        self.assertEqual(post.call_count, 1)
        sleeper.assert_not_called()

    def test_transient_failure_retries_and_uses_compact_schema(self):
        post = Mock(side_effect=[Response(503, {}), completion()])
        sleeper = Mock()
        rows, usage, _ = g.request_examples(self.config, self.part, 'B2', post, sleeper)
        self.assertEqual(rows, [ROW])
        self.assertEqual(usage['completion_tokens'], 30)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.kwargs['json']['model'], self.config['model'])
        self.assertIn('\nմիջին խավ |', post.call_args.kwargs['json']['messages'][1]['content'])

    def test_api_error_cannot_echo_authentication_token(self):
        token = 'fixture-token-for-offline-tests'
        response = Response(401, {'error': {'message': 'Invalid Bearer ' + token}})
        self.assertNotIn(token, g.error_text(response, self.config))

    def test_accepted_batch_is_checkpointed_with_real_newlines_and_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'data/examples').mkdir(parents=True)
            (root / 'data/words.json').write_text(json.dumps([{'lv': 'B2', 'w': [list(self.part[0])]}]))
            with patch.object(g, 'APP', temp), patch.object(g, 'load_values', return_value={'GITHUB_TOKEN': 'fixture-token'}), \
                    patch.object(g, 'request_examples', return_value=([ROW], {'completion_tokens': 30}, 'stop')), \
                    patch.object(sys, 'argv', ['gen_examples.py', '--level', 'B2', '--provider', 'github', '--include-multiword']):
                with self.assertRaises(SystemExit) as result:
                    g.main()
                self.assertEqual(result.exception.code, 0)
            lines = (root / 'data/examples/gen_b2.txt').read_text().splitlines()
            data = [line for line in lines if not line.startswith('#')]
            self.assertEqual(len(data), 1)
            self.assertEqual(len(data[0].split(' | ')), 8)
            report = json.loads((root / 'out/examples-b2-summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertEqual(report['accepted'], 1)


if __name__ == '__main__':
    unittest.main()
