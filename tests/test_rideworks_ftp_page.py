"""Synthetic FTP comparison and form security; no default or personal store."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import urlencode

from rideworks.store import Store
from rideworks.web import Application
from rideworks.ftp_page import comparison
from rideworks.ftp_history import snapshot
from ftp_fixture import seed_ftp


class FTPPageTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.target = Path(temp.name)/'store'
        self.app = Application(self.target)
        self.app.settings.port = 8765

    def seed(self):
        with Store(self.target) as store:
            seed_ftp(store,[('2020-01-01',190),('2020-06-01',250),('2020-12-31',220)])

    def submit(self, **changes):
        values = dict(nonce=self.app.settings.nonce, revision='0', date='2020-03-01', watts='210')
        values.update(changes)
        return self.app.post('/performance/ftp/add',urlencode(values).encode(),'http://127.0.0.1:8765')

    def test_empty_page_valid_and_manual_form_present(self):
        status,kind,body=self.app.get('/performance/ftp')
        self.assertEqual(status,200);self.assertEqual(kind,'text/html')
        self.assertIn(b'"rows":[]',body)
        self.assertIn(b'id="ftp-add"',body)
        self.assertIn(b'America/Los_Angeles',body)
        self.assertEqual(self.submit()[0],400)
        with Store(self.target) as store:self.assertEqual(snapshot(store)['rows'],[])

    def test_rounding_exact_comparison_calendar_and_uncertain_boundaries(self):
        self.seed()
        def point(i, raw, stamp='2020-03-02T00:30:00+00:00', absolute=True, day='2020-03-02'):
            return dict(activity_id=str(i),title='Synthetic',average_watts=raw,start_time=stamp,absolute_time=absolute,date_day=day)
        evidence=dict(points=[point(1,200),point(2,200.01),point(3,190),point(4,270,absolute=False,day='2020-06-01'),point(5,270,absolute=False,day='2019-12-20'),point(6,270,absolute=False,day='2020-03-02')],pending=2,missing_dates=1)
        with Store(self.target) as store, patch('rideworks.ftp_page.performance_history',return_value=evidence):
            result=comparison(store)
        a,b,c,d,e,f=result['points']
        self.assertEqual(a['date'],'2020-03-01');self.assertEqual(a['category'],'below')
        self.assertEqual(b['category'],'above');self.assertEqual(b['watts'],.95*200.01)
        self.assertEqual(c['watts'],180.5);self.assertEqual(c['proposed'],181)
        self.assertEqual(d['category'],'unavailable');self.assertEqual(d['ftp']['status'],'date_uncertain')
        self.assertEqual(e['category'],'unavailable');self.assertEqual(f['category'],'above')
        self.assertEqual(result['pending'],2)

    def test_save_stale_collision_and_security_preserve_history(self):
        self.seed()
        with Store(self.target) as store: before=snapshot(store)
        revision=str(before['revision'])
        self.assertEqual(self.submit(revision=revision,nonce='bad')[0],403)
        body=urlencode(dict(nonce=self.app.settings.nonce,revision=revision,date='2020-03-01',watts='210')).encode()
        self.assertEqual(self.app.post('/performance/ftp/add',body,'https://evil.example')[0],403)
        self.assertEqual(self.submit(revision=revision)[0],303)
        with Store(self.target) as store: after=snapshot(store)
        self.assertEqual(len(after['rows']),4)
        status,headers,error=self.submit(revision=revision,date='2020-04-01')
        self.assertEqual(status,400);self.assertIn('text/html',headers['Content-Type']);self.assertIn(b'changed',error)
        self.assertIn(b'2020-04-01',error)
        self.assertEqual(self.submit(revision=str(after['revision']))[0],400)
        for value in ['1.5','0','-1','NaN','99999999999999999999']:
            self.assertEqual(self.submit(revision=str(after['revision']),date='2020-04-01',watts=value)[0],400)
        with Store(self.target) as store:self.assertEqual(snapshot(store),after)
        self.assertIn(b'210',self.app.get('/performance/ftp')[2])
