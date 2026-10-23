import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError
from unittest.mock import patch
from web_server import make_server, live_client, REQUEST_TOKEN

class HistoryCredentialsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=make_server(0,Path(self.temp.name)/'cards.sqlite3')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.a=build_opener(HTTPCookieProcessor())
        self.b=build_opener(HTTPCookieProcessor())
        self.csrf=json.load(self.a.open(self.base+'/api/bootstrap'))['csrf']
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def post(self,client,route,body):
        return json.load(client.open(Request(self.base+route,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-CSRF-Token':self.csrf})))
    def test_missing_and_empty_rejected(self):
        with self.assertRaises(HTTPError) as e:self.post(self.a,'/api/quick-start',{})
        self.assertEqual(e.exception.code,401)
        with self.assertRaises(HTTPError):self.post(self.a,'/api/mcp-session',{'token':' '})
        with patch.dict('os.environ',{'MCD_TOKEN':'owner-secret'}):
            with self.assertRaises(ValueError):live_client()
    def test_sessions_isolated_disconnect_and_no_persistence(self):
        self.post(self.a,'/api/mcp-session',{'token':'user-a'})
        with self.assertRaises(HTTPError):self.post(self.b,'/api/quick-start',{})
        self.post(self.b,'/api/mcp-session',{'token':'user-b'})
        with patch('web_server.Client') as client, patch('web_server.business_data',return_value={'list':[]}):
            self.post(self.a,'/api/quick-start',{})
            self.assertEqual(client.call_args.args[0],'user-a')
            self.post(self.b,'/api/quick-start',{})
            self.assertEqual(client.call_args.args[0],'user-b')
        self.assertEqual(REQUEST_TOKEN.get(),'')
        self.post(self.a,'/api/mcp-session',{'disconnect':True})
        with self.assertRaises(HTTPError):self.post(self.a,'/api/quick-start',{})
        self.assertTrue(json.load(self.b.open(self.base+'/api/mcp-session'))['connected'])
        for p in Path(self.temp.name).glob('*'):
            self.assertNotIn(b'user-a',p.read_bytes());self.assertNotIn(b'user-b',p.read_bytes())
    def test_error_redacts_user_secret(self):
        self.post(self.a,'/api/mcp-session',{'token':'user-secret'})
        with patch('web_server.Client',side_effect=ValueError('bad user-secret')):
            with self.assertRaises(HTTPError) as e:self.post(self.a,'/api/quick-start',{})
        self.assertNotIn('user-secret',e.exception.read().decode())
