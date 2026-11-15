import json, pathlib, re, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Review(unittest.TestCase):
    def test_six_languages_and_client_consistency(self):
        register=json.loads((ROOT/'data/examples/dictionary_review.json').read_text())
        self.assertEqual(set(register['messages']),set(('ru','en','fr','es','de','pt')))
        source=(ROOT/'www/js/app.js').read_text()
        keys=json.loads(re.search(r'const LEXICAL_REVIEW=(.*);',source)[1])
        self.assertEqual(set(keys),set(register['entries']))
        self.assertTrue(all(v['status']=='uncertain' and v['issues'] for v in register['entries'].values()))
        self.assertIn('lexical_review["messages"][L]',(ROOT/'tools/build_seo.py').read_text())
if __name__=='__main__': unittest.main()
