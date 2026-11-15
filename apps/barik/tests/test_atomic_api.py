"""Real concurrent HTTP requests to four PHP workers; isolated SQLite and Dodo stub."""
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
        env = dict(os.environ, BARIK_DATA_DIR=str(cls.data), BARIK_PEPPER='atomic-tests', PHP_CLI_SERVER_WORKERS='4')
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
        cls.sql.close(); cls.log.close(); cls.tmp.cleanup()

    @classmethod
    def call(cls, route, payload=None, uid=1):
        req = urllib.request.Request(cls.url+route, data=None if payload is None else json.dumps(payload).encode(), headers={'X-Barik':'1','Content-Type':'application/json','Cookie':'barik_s='+str(uid)*40})
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

if __name__ == '__main__': unittest.main()
