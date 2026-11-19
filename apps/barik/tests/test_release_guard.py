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
        import shutil
        next_work=self.base/'next-release'
        shutil.copytree(self.work/'stage', next_work/'stage')
        shutil.copy2(self.work/'manifest.json', next_work/'manifest.json')
        self.work=next_work
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

    def test_batch_size_3000_and_split(self):
        import sys
        sys.path.insert(0, str(HELPER.parent))
        import deploy_site as deploy
        self.assertEqual(deploy.BATCH, 3000)
        self.assertEqual(deploy.RETRY_DELAYS, (4, 8, 15))
        todo = {f'en/w/w{i}.html': f'/tmp/w{i}.html' for i in range(6500)}
        todo['index.html'] = '/tmp/index.html'
        batches = deploy.split_batches(todo)
        self.assertEqual(len(batches), 4)
        self.assertTrue(all(len(b) <= 3000 for b in batches))
        self.assertIn('index.html', batches[-1])

    def test_retry_backoff_release_control_and_uapi(self):
        import sys, requests
        sys.path.insert(0, str(HELPER.parent))
        import deploy_site as deploy
        from unittest.mock import patch, MagicMock
        sleeps = []
        r503 = MagicMock(status_code=503)
        r503.raise_for_status.side_effect = requests.HTTPError('503', response=r503)
        r502 = MagicMock(status_code=502)
        r502.raise_for_status.side_effect = requests.HTTPError('502', response=r502)
        r200 = MagicMock(status_code=200)
        r200.json.return_value = {'ok': True}
        with patch.object(deploy.time, 'sleep', side_effect=sleeps.append), \
             patch.object(deploy.requests, 'post', side_effect=[r503, requests.Timeout('t'), r502, r200]):
            deploy.release_control('prepare', {'url': 'https://example.com/r.php', 'token': 'tok'})
        self.assertEqual(sleeps, [4, 8, 15])
        # CPanel.uapi also retries on 504 + Timeout with (4, 8, 15)
        cp = deploy.CPanel('host.example', 'example.com', 'u', '', 'tok')
        cp.token = ''
        sleeps2 = []
        r504 = MagicMock(status_code=504)
        r504.raise_for_status.side_effect = requests.HTTPError('504', response=r504)
        rok = MagicMock(status_code=200)
        rok.json.return_value = {'status': 1, 'data': []}
        with patch.object(deploy.time, 'sleep', side_effect=sleeps2.append), \
             patch.object(cp.s, 'post', side_effect=[r504, requests.Timeout('t'), r503, rok]):
            res = cp.uapi('Fileman', 'upload_files', files={'file-1': ('a.zip', b'PK', 'application/zip')}, dir='work')
        self.assertEqual(res['status'], 1)
        self.assertEqual(sleeps2, [4, 8, 15])

    def test_guarded_release_finally_cleans_up_on_upload_error(self):
        import os, sys
        sys.path.insert(0, str(HELPER.parent))
        import deploy_site as deploy
        from unittest.mock import patch
        unlinked = []
        calls = []
        class FakeCP:
            def uapi(self, mod, fn, files=None, **kw):
                if fn == 'upload_files' and kw.get('dir') != 'public_html':
                    raise RuntimeError('chunk boom')
                return {'status': 1, 'data': []}
            def api2(self, mod, fn, **kw):
                if kw.get('op') == 'unlink':
                    unlinked.append(kw.get('sourcefiles'))
                return {'cpanelresult': {'event': {'result': 1}}}
            def ok(self, j, what): return j
        def fake_ctrl(action, creds=None):
            calls.append(action)
            if action == 'finalize':
                raise RuntimeError('endpoint gone')
        rel_file = self.base / 'release-private.json'
        stage_file = self.base / 'index.html'
        stage_file.write_text('hi')
        with patch.dict(os.environ, {'BARIK_HOST_TOKEN': 'sec', 'BARIK_HOST_DOMAIN': 'example.com'}), \
             patch.object(deploy, 'RELEASE', str(rel_file)), \
             patch.object(deploy, 'WORK', str(self.base / 'zips')), \
             patch.object(deploy, 'release_control', side_effect=fake_ctrl):
            with self.assertRaises(RuntimeError):
                deploy.guarded_release(FakeCP(), '/home/u/public_html', {'index.html': str(stage_file)})
        self.assertEqual(calls, ['prepare', 'finalize'])
        self.assertEqual(len(unlinked), 1)
        self.assertRegex(unlinked[0], r'^/home/u/public_html/barik-release-[0-9a-f]{24}\.php$')
        self.assertFalse(rel_file.exists())

    def test_recover_release_unlinks_expired_orphan(self):
        import os, sys
        sys.path.insert(0, str(HELPER.parent))
        import deploy_site as deploy
        from unittest.mock import patch
        unlinked = []
        class FakeCP:
            def uapi(self, mod, fn, **kw):
                return {'status': 1, 'data': [{'file': 'barik-release-' + ('b' * 24) + '.php', 'absdir': '/home/u/public_html'}]}
            def api2(self, mod, fn, **kw):
                if kw.get('op') == 'unlink':
                    unlinked.append(kw.get('sourcefiles'))
                return {'cpanelresult': {'event': {'result': 1}}}
            def ok(self, j, what): return j
        with patch.dict(os.environ, {'BARIK_HOST_TOKEN': 'sec', 'BARIK_HOST_DOMAIN': 'example.com'}), \
             patch.object(deploy, 'RELEASE', str(self.base / 'absent')), \
             patch.object(deploy, 'STATE', str(self.base / 'state.json')), \
             patch.object(deploy, 'release_control', side_effect=RuntimeError('410 Gone')):
            deploy.recover_release(FakeCP())
        self.assertEqual(unlinked, ['/home/u/public_html/barik-release-' + ('b' * 24) + '.php'])

    def test_ttl_self_destruct_410(self):
        import os, socket, time, urllib.request, urllib.error
        ep = self.root / 'barik-release-expired.php'
        ep.write_text(HELPER.read_text().replace('__TOKEN__', 'tok').replace('__ID__', 'expired'))
        old = time.time() - 1300
        os.utime(ep, (old, old))
        sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
        srv = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', str(self.root)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            code = None
            for _ in range(30):
                try:
                    req = urllib.request.Request(f'http://127.0.0.1:{port}/barik-release-expired.php?action=prepare',
                                                 method='POST', headers={'X-Release-Token': 'tok'})
                    urllib.request.urlopen(req, timeout=2)
                except urllib.error.HTTPError as e:
                    code = e.code; break
                except Exception:
                    time.sleep(0.1)
            self.assertEqual(code, 410)
            self.assertFalse(ep.exists())
        finally:
            srv.terminate(); srv.wait(timeout=5)

if __name__=='__main__': unittest.main()
