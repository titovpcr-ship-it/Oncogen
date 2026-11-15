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
        (self.root/'z.js').write_text('old-z'); (self.work/'stage/z.js').write_text('new-z')
        manifest=json.loads((self.work/'manifest.json').read_text()); manifest['z.js']=hashlib.sha256(b'new-z').hexdigest()
        (self.work/'manifest.json').write_text(json.dumps(manifest))
        # Pause inside rename after replacing the first file, while the gate and lock are held.
        instrumented=self.base/'guard.php'
        text=HELPER.read_text().replace('!rename($tmp, $path)', '!test_rename($tmp, $path)')
        text += '\nfunction test_rename($a,$b){$ok=rename($a,$b); if(str_ends_with($b,"/app.js") && !str_contains($b,"/old/")){echo "MID_WRITE\\n"; fflush(STDOUT); fread(STDIN,1);} return $ok;}\n'
        instrumented.write_text(text)
        script='require '+json.dumps(str(instrumented))+'; release_action('+','.join(json.dumps(str(x)) for x in (self.root,self.work,'activate','release.php'))+');'
        proc=subprocess.Popen(['php','-r',script],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertEqual(proc.stdout.readline().strip(),b'MID_WRITE')
        proc.kill(); proc.communicate(timeout=5)
        self.assertIn('503',(self.root/'.htaccess').read_text())
        self.assertEqual(self.action('rollback').returncode,0)
        self.assertEqual((self.root/'app.js').read_text(),'old')
        # A subsequent release recomputes all fingerprints after recovery invalidates state.
        import sys, importlib.util, os
        sys.path.insert(0,str(HELPER.parent))
        import deploy_site as deploy
        from unittest.mock import patch
        state=self.base/'state.json'; state.write_text(json.dumps({name:deploy.sha(self.work/'stage'/name) for name in ('app.js','z.js')}))
        def control(action, credentials=None):
            if action=='rollback':
                self.assertEqual(self.action('rollback').returncode,0)
                if state.exists(): state.unlink()
        class CP:
            def uapi(self,*args,**kwargs): return {'status':1,'data':[{'file':'barik-release-'+('a'*24)+'.php'}]}
            def ok(self,*args): return None
        with patch.dict(os.environ,{'BARIK_HOST_TOKEN':'test','BARIK_HOST_DOMAIN':'example.com'}), patch.object(deploy,'RELEASE',str(self.base/'absent')), patch.object(deploy,'release_control',side_effect=control), patch.object(deploy,'STATE',str(state)), patch.object(deploy,'scan',return_value={name:str(self.work/'stage'/name) for name in ('app.js','z.js')}):
            files, cached, hashes, todo, gone = deploy.release_plan(CP())
        self.assertFalse(state.exists())
        self.assertEqual(set(todo),{'app.js','z.js'})
        (self.work/'journal.json').unlink()
        self.assertEqual(self.action('activate').returncode,0)
        self.assertEqual((self.root/'app.js').read_text(),'new')
    def test_lock_is_shared_between_release_ids(self):
        import fcntl, time
        other=self.base/'another-release'
        lock=open(self.base/'.barik-release.lock','w')
        fcntl.flock(lock,fcntl.LOCK_EX)
        script='require '+json.dumps(str(HELPER))+'; release_action('+','.join(json.dumps(str(x)) for x in (self.root,other,'prepare','other.php'))+');'
        proc=subprocess.Popen(['php','-r',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            time.sleep(.15); self.assertIsNone(proc.poll())
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN); lock.close()
        stdout,stderr=proc.communicate(timeout=5)
        self.assertEqual(proc.returncode,0,stderr)
        self.assertTrue((other/'stage').exists())

    def test_rotation_keeps_three_finalized_releases(self):
        import os
        for i in range(5):
            d=self.base/f'barik-release-{i}'; d.mkdir(); (d/'finalized').write_text('done'); os.utime(d/'finalized',(100+i,100+i))
        (self.root/'release.php').write_text('endpoint')
        self.assertEqual(self.action('finalize').returncode,0)
        self.assertEqual(len(list(self.base.glob('barik-release-*'))),3)
        self.assertFalse((self.root/'release.php').exists())

    def test_config_rejected(self):
        (self.work/'manifest.json').write_text(json.dumps({'api/config.php':'x'}))
        self.assertNotEqual(self.action('activate').returncode,0)
        self.assertEqual((self.root/'api/config.php').read_text(),'secret')
if __name__=='__main__': unittest.main()
