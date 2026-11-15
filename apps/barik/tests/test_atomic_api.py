"""Real concurrent HTTP requests to four PHP workers; isolated SQLite and Dodo stub."""
import base64, hmac, http.server, threading
import concurrent.futures, hashlib, json, os, pathlib, socket, sqlite3, subprocess, tempfile, time, unittest, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[1]

class AtomicAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = pathlib.Path(cls.tmp.name)
        (cls.data / 'api').symlink_to(ROOT / 'server/api', target_is_directory=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        cls.url = f'http://127.0.0.1:{port}/api/?r='
        cls.dodo_state = {'status':200, 'calls':0}
        class Dodo(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                cls.dodo_state['calls'] += 1
                time.sleep(.05)
                payload = {'subscription_id':'sub_atomic','status':'active','product_id':'prod_month',
                           'next_billing_date':'2030-01-01T00:00:00Z','customer':{'email':'1@example.com'}}
                if self.path.startswith('/payments/'):
                    payload = {'payment_id':'pay_hook','status':'succeeded','metadata':{'gift':'1','uid':'1','months':'3',
                               'sig':hmac.new(b'atomic-tests',b'uid:1',hashlib.sha256).hexdigest()[:32]}}
                self.send_response(cls.dodo_state['status']); self.end_headers(); self.wfile.write(json.dumps(payload).encode())
            def log_message(self, *args): pass
        cls.stub = http.server.ThreadingHTTPServer(('127.0.0.1',0),Dodo)
        threading.Thread(target=cls.stub.serve_forever,daemon=True).start()
        env = dict(os.environ, BARIK_DODO_API_KEY='test',BARIK_DODO_PRODUCT_MONTH='prod_month',
                   BARIK_DODO_API=f'http://127.0.0.1:{cls.stub.server_port}',
                   BARIK_DODO_WEBHOOK_SECRET='whsec_'+base64.b64encode(b'webhook-test').decode(), BARIK_DATA_DIR=str(cls.data), BARIK_PEPPER='atomic-tests', PHP_CLI_SERVER_WORKERS='4')
        cls.log = open(cls.data / 'php.log', 'w')
        cls.proc = subprocess.Popen(['php', '-S', f'127.0.0.1:{port}', '-t', str(cls.data), str(ROOT / 'tests/php_router.php')], env=env, stdout=cls.log, stderr=cls.log, start_new_session=True)
        for _ in range(100):
            try:
                cls.call('me'); break
            except (OSError, ValueError): time.sleep(.05)
        else: raise RuntimeError('PHP did not start')
        cls.sql = sqlite3.connect(cls.data / 'barik.sqlite', timeout=10)
        for uid in (1, 2):
            cls.sql.execute('INSERT INTO users(id,email,nick,nick_key,created) VALUES(?,?,?,?,?)', (uid,f'{uid}@example.com',f'user{uid}',f'user{uid}',int(time.time())))
            cls.sql.execute('INSERT INTO sessions(token,user_id,created,expires) VALUES(?,?,?,?)', (hashlib.sha256((str(uid)*40).encode()).hexdigest(),uid,int(time.time()),int(time.time())+3600))
        cls.sql.commit()

    @classmethod
    def tearDownClass(cls):
        import signal
        os.killpg(cls.proc.pid, signal.SIGTERM); cls.proc.wait(timeout=10)
        cls.stub.shutdown(); cls.stub.server_close(); cls.sql.close(); cls.log.close(); cls.tmp.cleanup()

    @classmethod
    def call(cls, route, payload=None, uid=1, event_id=None):
        req = urllib.request.Request(cls.url+route, data=None if payload is None else json.dumps(payload).encode(), headers={'X-Barik':'1','Content-Type':'application/json','Cookie':'barik_s='+str(uid)*40})
        if event_id:
            ts = str(int(time.time()))
            sig = base64.b64encode(hmac.new(b'webhook-test',event_id.encode()+b'.'+ts.encode()+b'.'+req.data,hashlib.sha256).digest()).decode()
            req.add_header('webhook-id',event_id); req.add_header('webhook-timestamp',ts); req.add_header('webhook-signature','v1,'+sig)
        try:
            with urllib.request.urlopen(req, timeout=15) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as r: return r.code, json.load(r)

    def parallel(self, calls):
        # Hold the writer lock until all HTTP clients have started, then release together.
        self.sql.execute('BEGIN IMMEDIATE')
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(calls)) as pool:
            futures = [pool.submit(self.call, *args) for args in calls]
            time.sleep(.2); self.sql.commit()
            return [f.result() for f in futures]

    def gift(self, code, pay):
        self.sql.execute('INSERT INTO gifts(code,pay_id,buyer,months,created) VALUES(?,?,1,3,?)',(code,pay,int(time.time())))
        self.sql.commit()

    def test_h1_one_recipient(self):
        self.gift('BARIK-AAAA-BBBB','pay_one')
        results = self.parallel([('gift_redeem',{'code':'BARIK-AAAA-BBBB'},uid) for uid in (1,2)])
        self.assertEqual(sorted(r[0] for r in results),[200,400])
        self.assertEqual(self.sql.execute('SELECT COUNT(*) FROM users WHERE gift_until > 0').fetchone()[0],1)

    def test_h1_stacking_and_retry(self):
        self.sql.execute('UPDATE users SET gift_until=0'); self.sql.commit()
        for i in (1,2): self.gift(f'BARIK-CCCC-DDD{i}',f'pay_stack{i}')
        before = int(time.time())
        results = self.parallel([('gift_redeem',{'code':f'BARIK-CCCC-DDD{i}'},1) for i in (1,2)])
        self.assertEqual([r[0] for r in results],[200,200])
        until = self.sql.execute('SELECT gift_until FROM users WHERE id=1').fetchone()[0]
        self.assertAlmostEqual(until-before,180*86400,delta=5)
        self.call('gift_redeem',{'code':'BARIK-CCCC-DDD1'})
        self.assertEqual(self.sql.execute('SELECT gift_until FROM users WHERE id=1').fetchone()[0],until)

    def test_h1_rollback(self):
        self.gift('BARIK-EEEE-FFFF','pay_failure')
        self.sql.execute("CREATE TRIGGER fail_gift BEFORE UPDATE OF gift_until ON users BEGIN SELECT RAISE(ABORT,'injected failure'); END"); self.sql.commit()
        try:
            self.assertEqual(self.call('gift_redeem',{'code':'BARIK-EEEE-FFFF'})[0],500)
            self.assertIsNone(self.sql.execute("SELECT used_by FROM gifts WHERE pay_id='pay_failure'").fetchone()[0])
        finally:
            self.sql.execute('DROP TRIGGER fail_gift'); self.sql.commit()

    def test_h2_concurrent_versions(self):
        self.sql.execute('DELETE FROM progress'); self.sql.commit()
        for rev in (0, 1):
            payloads = [{'rev':rev,'data':json.dumps({'s':{'w':{str(i):i}}})} for i in (1,2)]
            results = self.parallel([('sync',p,1) for p in payloads])
            self.assertEqual(sorted(r[0] for r in results),[200,409])
            current = self.call('sync')[1]
            conflict = next(r[1] for r in results if r[0]==409)
            self.assertEqual(current['rev'],rev+1)
            self.assertEqual(conflict['data'],current['data'])
        merged = json.dumps({'s':{'w':{'1':1,'2':2}}})
        self.assertEqual(self.call('sync',{'rev':2,'data':merged})[0],200)
        self.assertEqual(self.call('sync')[1]['data'],merged)

    def test_h2_rollback(self):
        previous = self.call('sync')[1]
        self.sql.execute("CREATE TRIGGER fail_sync BEFORE UPDATE ON progress BEGIN SELECT RAISE(ABORT,'injected'); END"); self.sql.commit()
        try:
            self.assertEqual(self.call('sync',{'rev':previous['rev'],'data':'{"s":{}}'})[0],500)
            self.assertEqual(self.call('sync')[1],previous)
        finally:
            self.sql.execute('DROP TRIGGER fail_sync'); self.sql.commit()

    def test_h3_concurrent_duplicate(self):
        before = self.dodo_state['calls']
        payload = {'data':{'subscription_id':'sub_atomic'}}
        results = self.parallel([('dodo',payload,1,'evt_same')]*2)
        self.assertEqual([r[0] for r in results],[200,200])
        self.assertEqual(sum(bool(r[1].get('dup')) for r in results),1)
        self.assertEqual(self.dodo_state['calls']-before,1)

    def test_h3_transient_and_rollback(self):
        for code in (429,500):
            self.dodo_state['status']=code
            for kind in ('sub','gift'):
                event = f'evt_{code}_{kind}'
                data = {'subscription_id':'sub_atomic'} if kind=='sub' else {'payment_id':'pay_hook','metadata':{'gift':'1'}}
                self.assertEqual(self.call('dodo',{'data':data},1,event)[0],503)
                self.assertEqual(self.sql.execute('SELECT COUNT(*) FROM events WHERE id=?',('dodo:'+event,)).fetchone()[0],0)
        self.dodo_state['status']=200
        payload = {'data':{'subscription_id':'sub_atomic'}}
        self.sql.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'injected'); END"); self.sql.commit()
        old = self.sql.execute('SELECT sub_at FROM users WHERE id=1').fetchone()[0]
        try:
            self.assertEqual(self.call('dodo',payload,1,'evt_crash')[0],500)
            self.assertEqual(self.sql.execute('SELECT sub_at FROM users WHERE id=1').fetchone()[0],old)
        finally:
            self.sql.execute('DROP TRIGGER fail_event'); self.sql.commit()
        results = self.parallel([('dodo',payload,1,'evt_crash')]*2)
        self.assertEqual([r[0] for r in results],[200,200])
        gift = {'data':{'payment_id':'pay_hook','metadata':{'gift':'1'}}}
        self.assertEqual([r[0] for r in self.parallel([('dodo',gift,1,'evt_gift')]*2)],[200,200])
        self.assertEqual(self.sql.execute("SELECT COUNT(*) FROM gifts WHERE pay_id='pay_hook'").fetchone()[0],1)
        self.assertEqual(self.call('dodo',payload)[0],401)

if __name__ == '__main__': unittest.main()
