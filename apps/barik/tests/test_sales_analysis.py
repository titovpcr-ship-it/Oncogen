"""Anonymous analytics: real SQLite/PHP HTTP, filtering, idempotency and signed Dodo callback."""
import json,time,uuid,urllib.request,urllib.error,unittest,hmac,hashlib
import test_atomic_api as harness

class Sales(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        harness.AtomicAPI.setUpClass();cls.api=harness.AtomicAPI()
    @classmethod
    def tearDownClass(cls):harness.AtomicAPI.tearDownClass()
    def request(self,route,data=None,ua='BarikBrowser/1',key=True):
        req=urllib.request.Request(self.api.url+route,data=None if data is None else json.dumps(data).encode(),headers={'User-Agent':ua,'Content-Type':'application/json',**({'X-Barik-Key':'m9x4k2p7-v9q3r8t5w2y6'} if key else {})})
        try:
            with urllib.request.urlopen(req) as r:return r.status,r.read(),r.headers
        except urllib.error.HTTPError as r:return r.code,r.read(),r.headers
    def setUp(self):
        self.request('sales_analysis');self.sql=self.api.sql
        self.sql.execute('DELETE FROM sales_events');self.sql.execute('DELETE FROM sales_sessions');self.sql.execute('DELETE FROM events');self.sql.execute('DELETE FROM hits');self.sql.commit()
        self.api.dodo_state.pop('payment',None)
    def ev(self,sid,event,**extra):return dict(sid=sid,eid=uuid.uuid4().hex,event=event,t=int(time.time()),lang='ru',device='mobile',source='direct',**extra)
    def analysis(self,query=''):
        status,body,_=self.request('sales_analysis'+query);self.assertEqual(status,200);return json.loads(body)
    def test_auth_bot_validation_and_dedup(self):
        self.assertEqual(self.request('sales_analysis',key=False)[0],404)
        sid=uuid.uuid4().hex;e=self.ev(sid,'session_start')
        self.assertEqual(self.request('sales_ev',[e],ua='Googlebot')[0],204)
        self.assertEqual(self.analysis()['kpi']['sessions'],0)
        self.assertEqual(self.request('sales_ev',[e,e])[0],204)
        self.request('sales_ev',[e])
        self.assertEqual(self.sql.execute('SELECT COUNT(*) FROM sales_events').fetchone()[0],1)
        self.request('sales_ev',[dict(e,eid='server:paid',event='payment_success'),dict(e,sid='invalid')])
        self.assertEqual(self.analysis()['kpi']['sessions'],1)
        self.assertEqual(self.analysis()['kpi']['paid'],0)
    def test_filters_medians_reasons_and_client_success(self):
        a,b=uuid.uuid4().hex,uuid.uuid4().hex
        self.request('sales_ev',[self.ev(a,'session_start'),self.ev(a,'activation'),self.ev(a,'paywall_view'),self.ev(a,'paywall_close',pw_sec=12),self.ev(a,'payment_success')])
        self.request('sales_ev',[dict(self.ev(b,'session_start'),lang='pt',device='desktop',t=int(time.time())-2*86400),dict(self.ev(b,'paywall_close',pw_sec=30),lang='pt',device='desktop',t=int(time.time())-2*86400)])
        d=self.analysis('&period=7d');self.assertEqual(d['median_pw_sec'],21);self.assertEqual(d['kpi']['paid'],0)
        self.assertEqual(sum(r['n'] for r in d['reasons']),2)
        self.assertEqual(self.analysis('&period=24h')['kpi']['sessions'],1)
        self.assertEqual(self.analysis('&lang=PT&device=desktop')['kpi']['sessions'],1)
        self.assertEqual(self.analysis('&lang=RU&device=desktop')['kpi']['sessions'],0)
        self.assertEqual(len(d['funnel']),6);self.assertEqual(len(d['cuts']),4)
    def test_verified_payment_webhook_and_duplicate(self):
        sid=uuid.uuid4().hex;self.request('sales_ev',[self.ev(sid,'session_start'),self.ev(sid,'checkout_start')])
        sig=hmac.new(b'atomic-tests',b'uid:1',hashlib.sha256).hexdigest()[:32]
        self.api.dodo_state['payment']={'metadata':{'sales_sid':sid,'uid':'1','sig':sig,'lang':'ru'}}
        payload={'type':'payment.succeeded','data':{'subscription_id':'sub_atomic','payment_id':'pay_hook'}}
        for _ in range(2):self.assertEqual(self.api.call('dodo',payload,event_id='sales_paid')[0],200)
        d=self.analysis();self.assertEqual(d['kpi']['paid'],1);self.assertEqual(d['recent'],[])
        self.assertEqual(self.sql.execute("SELECT COUNT(*) FROM sales_events WHERE verified=1 AND event='payment_success'").fetchone()[0],1)
    def test_post_commit_failure_retry_repairs_analytics(self):
        sid=uuid.uuid4().hex;self.request('sales_ev',[self.ev(sid,'session_start')])
        sig=hmac.new(b'atomic-tests',b'uid:1',hashlib.sha256).hexdigest()[:32]
        self.api.dodo_state['payment']={'metadata':{'sales_sid':sid,'uid':'1','sig':sig}}
        self.sql.execute("CREATE TRIGGER sales_fail BEFORE INSERT ON sales_events WHEN NEW.verified=1 BEGIN SELECT RAISE(ABORT,'injected analytics failure'); END");self.sql.commit()
        payload={'type':'payment.succeeded','data':{'subscription_id':'sub_atomic','payment_id':'pay_hook'}}
        try:
            self.assertEqual(self.api.call('dodo',payload,event_id='sales_retry')[0],500)
            self.assertIsNotNone(self.sql.execute("SELECT id FROM events WHERE id='dodo:sales_retry'").fetchone())
        finally:self.sql.execute('DROP TRIGGER sales_fail');self.sql.commit()
        self.assertEqual(self.api.call('dodo',payload,event_id='sales_retry')[0],200)
        self.assertEqual(self.analysis()['kpi']['paid'],1)

if __name__=='__main__':unittest.main()
