import hashlib, json, pathlib, subprocess, tempfile, unittest
HELPER = pathlib.Path(__file__).resolve().parents[1] / 'tools/release_guard.php'
class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = pathlib.Path(self.tmp.name)
        self.root = self.base/'public_html'; self.work = self.base/'private'
        self.root.mkdir(); self.work.mkdir(); (self.work/'stage').mkdir()
        (self.root/'.htaccess').write_text('# old rules')
        (self.root/'app.js').write_text('old'); (self.root/'api').mkdir(); (self.root/'api/config.php').write_text('secret')
        (self.work/'stage/app.js').write_text('new')
        (self.work/'manifest.json').write_text(json.dumps({'app.js':hashlib.sha256(b'new').hexdigest()}))
    def tearDown(self): self.tmp.cleanup()
    def action(self, name):
        script = 'require '+json.dumps(str(HELPER))+'; release_action('+','.join(json.dumps(str(x)) for x in (self.root,self.work,name,'release.php'))+');'
        return subprocess.run(['php','-r',script],capture_output=True)
    def test_activate_and_rollback(self):
        self.assertEqual(self.action('activate').returncode,0)
        self.assertEqual((self.root/'app.js').read_text(),'new')
        self.assertEqual(self.action('rollback').returncode,0)
        self.assertEqual((self.root/'app.js').read_text(),'old')
        self.assertEqual((self.root/'.htaccess').read_text(),'# old rules')
        self.assertEqual((self.root/'api/config.php').read_text(),'secret')
    def test_bad_stage_leaves_live_unchanged(self):
        (self.work/'stage/app.js').write_text('corrupt')
        self.assertNotEqual(self.action('activate').returncode,0)
        self.assertEqual((self.root/'app.js').read_text(),'old')
        self.assertEqual((self.root/'.htaccess').read_text(),'# old rules')
    def test_write_failure_rolls_back(self):
        # A directory at the destination forces rename failure after the first file changed.
        (self.root/'z.js').mkdir(); (self.work/'stage/z.js').write_text('z')
        m=json.loads((self.work/'manifest.json').read_text()); m['z.js']=hashlib.sha256(b'z').hexdigest()
        (self.work/'manifest.json').write_text(json.dumps(m))
        self.assertNotEqual(self.action('activate').returncode,0)
        self.assertEqual((self.root/'app.js').read_text(),'old')
        self.assertEqual((self.root/'.htaccess').read_text(),'# old rules')
    def test_resume_after_process_loss(self):
        self.action('activate')
        (self.root/'.htaccess').write_text('RewriteRule ^ - [R=503,L]')
        self.assertEqual(self.action('rollback').returncode,0)
        self.assertEqual((self.root/'app.js').read_text(),'old')
    def test_config_rejected(self):
        (self.work/'manifest.json').write_text(json.dumps({'api/config.php':'x'}))
        self.assertNotEqual(self.action('activate').returncode,0)
        self.assertEqual((self.root/'api/config.php').read_text(),'secret')
if __name__=='__main__': unittest.main()
