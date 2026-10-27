import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import connector as m

FAKE = '''#!/usr/bin/env python3
import json, pathlib, sys, time
prompt=sys.stdin.read()
if 'SILENT_TEST' in prompt.split('Current user task:')[-1]: time.sleep(20)
if 'SLOW_TEST' in prompt.split('Current user task:')[-1]:
 for i in range(40):
  print('working', flush=True); time.sleep(.2)
if 'FAIL_TEST' in prompt.split('Current user task:')[-1]: sys.exit(7)
result='FAKE_OK '+prompt
if '-o' in sys.argv:
 pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text(result)
 pathlib.Path('artifact.txt').write_text('created')
 print(json.dumps({'type':'done'}))
else: print(json.dumps({'type':'result','result':result,'is_error':False}))
'''

class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        m.STATE = self.root / 'state'
        m.WORKSPACE = self.root / 'work'
        self.old = os.environ.copy()
        os.environ['MODEL_CONNECTOR_STATE'] = str(m.STATE)
        os.environ['MODEL_CONNECTOR_WORKSPACE'] = str(m.WORKSPACE)
        os.environ['MODEL_CONNECTOR_AUTOSTART'] = '0'
        os.environ['MODEL_CONNECTOR_MODELS'] = str(self.root / 'no-models.json')
        for tool in ('codex', 'claude'):
            p = self.root / tool
            p.write_text(FAKE)
            p.chmod(0o700)
        os.environ['PATH'] = str(self.root) + os.pathsep + os.environ['PATH']

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)
        self.tmp.cleanup()

    def start(self, prompt='hello', **kwargs):
        return m.call('start_task', dict(bot_id='bot', prompt=prompt, **kwargs))

    def finish(self, task):
        for _ in range(100):
            t = m.get_task(task['id'])
            if t['status'] not in m.ACTIVE:
                return t
            time.sleep(.1)
        self.fail('worker did not finish')

    def test_switch_preserves_history_and_bot_default(self):
        first = self.finish(self.start('remember secret pineapple'))
        self.assertEqual(first['status'], 'completed')
        self.assertIn('artifact.txt', first['artifacts']['changed'])
        m.call('set_bot_default', {'bot_id': 'bot', 'model': 'claude'})
        second = self.finish(self.start('what did I say?'))
        self.assertEqual(second['model'], 'claude')
        self.assertIn('secret pineapple', second['result'])
        third = self.finish(self.start('override', model='codex'))
        self.assertEqual(third['model'], 'codex')
        self.assertFalse(third['completion_verified'])

    def test_stall_and_durable_alert(self):
        t = self.finish(self.start('SILENT_TEST', idle_seconds=1, timeout_seconds=5))
        self.assertEqual(t['status'], 'stalled')
        events = m.call('list_events', {'bot_id': 'bot'})['events']
        self.assertIn('stalled', [e['kind'] for e in events])
        self.assertEqual(events, m.call('list_events', {'bot_id': 'bot'})['events'])
        m.call('ack_events', {'bot_id': 'other', 'event_ids': [e['id'] for e in events]})
        self.assertEqual(events, m.call('list_events', {'bot_id': 'bot'})['events'])
        m.call('ack_events', {'bot_id': 'bot', 'event_ids': [e['id'] for e in events]})
        self.assertEqual([], m.call('list_events', {'bot_id': 'bot'})['events'])

    def test_timeout_despite_activity(self):
        t = self.finish(self.start('SLOW_TEST', idle_seconds=1, timeout_seconds=1.2))
        self.assertEqual(t['status'], 'timed_out')

    def test_plan_without_required_code_fails(self):
        t = self.finish(self.start(required_artifacts=['app.py']))
        self.assertEqual(t['status'], 'failed')
        self.assertIn('app.py', t['error'])

    def test_required_file_passes(self):
        self.assertEqual(self.finish(self.start(required_artifacts=['artifact.txt']))['status'], 'completed')

    def test_provider_failure(self):
        self.assertEqual(self.finish(self.start('FAIL_TEST'))['status'], 'failed')

    def test_cancel_and_single_active_task(self):
        t = self.start('SILENT_TEST')
        with self.assertRaises(ValueError): self.start()
        m.call('cancel_task', {'task_id': t['id']})
        time.sleep(1.5)
        self.assertEqual(m.get_task(t['id'])['status'], 'cancelled')

    def test_worker_loss(self):
        with m.db() as c:
            c.execute("INSERT INTO tasks(id,bot,status,heartbeat) VALUES('lost','bot','running',0)")
        self.assertEqual(m.get_task('lost')['status'], 'interrupted')
        self.assertEqual(m.call('list_events', {'bot_id': 'bot'})['events'][0]['kind'], 'interrupted')

    def test_recovery_and_event_wakeup(self):
        task = self.start('SILENT_TEST', idle_seconds=2, timeout_seconds=5)
        self.assertEqual(m.call('list_tasks', {'bot_id': 'bot'})['tasks'][0]['id'], task['id'])
        self.assertEqual(m.call('list_tasks', {'bot_id': 'other'})['tasks'], [])
        output = subprocess.run(
            [sys.executable, str(m.ROOT/'connector.py'), 'wait-event', task['id']],
            capture_output=True, text=True, check=True, timeout=10)
        wakeup = json.loads(output.stdout)
        self.assertTrue(wakeup['unacknowledged_events'])
        self.assertEqual(wakeup['task']['status'], 'stalled')
        self.assertEqual([e['kind'] for e in wakeup['unacknowledged_events']], ['stalled'])
        self.assertTrue(m.call('list_events', {'bot_id': 'bot'})['events'])
        self.finish(task)
        self.assertEqual(m.call('list_tasks', {'bot_id': 'bot'})['tasks'], [])
        events = m.call('list_events', {'bot_id': 'bot'})['events']
        m.call('ack_events', {'bot_id': 'bot', 'event_ids': [e['id'] for e in events]})
        self.assertEqual(m.wait_event(task['id'])['unacknowledged_events'], [])

    def test_isolation_and_input_validation(self):
        m.call('set_bot_memory', {'bot_id': 'bot', 'memory': 'private memory'})
        self.finish(self.start('private conversation'))
        other = self.finish(m.call('start_task', {'bot_id': '../../other', 'prompt': 'hello'}))
        self.assertNotIn('private memory', other['result'])
        self.assertNotIn('private conversation', other['result'])
        self.assertTrue(Path(other['artifacts']['workspace']).is_relative_to(m.WORKSPACE))
        with self.assertRaises(ValueError): self.start(model='unknown')
        with self.assertRaises(ValueError): self.start(idle_seconds=0)

    def server(self, responses=None):
        self.requests = []
        replies = list(responses or [])
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                owner.requests.append((self.path, dict(self.headers), json.loads(
                    self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(replies.pop(0) if replies else 200)
                self.end_headers()
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return 'http://127.0.0.1:' + str(server.server_port)

    def configure(self, url, bot='bot', **extra):
        os.environ['TEST_SENDER_KEY'] = 'private-sender-key'
        return m.call('set_bot_webhook', dict(bot_id=bot, url=url,
                                             key_env='TEST_SENDER_KEY', **extra))

    def test_webhook_alert_filter_routing_and_durable_receipts(self):
        url = self.server()
        self.configure(url + '/owner')
        self.configure(url + '/other', 'other')
        with m.db() as c:
            for kind in ('started', 'progress', 'inactivity') + m.ALERTS:
                m.event(c, {'id': 'task', 'bot': 'bot'}, kind, 'SECRET PROMPT')
            m.event(c, {'id': 'other-task', 'bot': 'other'}, 'completed', 'secret')
        self.assertFalse(m.deliver_alerts())
        self.assertEqual(len(self.requests), 6)
        for path, headers, body in self.requests:
            self.assertEqual(headers['Authorization'], 'Bearer private-sender-key')
            self.assertEqual(path, '/owner' if body['bot_id'] == 'bot' else '/other')
            self.assertNotIn('SECRET', json.dumps(body))
            self.assertIn('Idempotency-Key', headers)
        m.deliver_alerts()
        self.assertEqual(len(self.requests), 6)
        # Reopening the database and acknowledging does not erase receipts.
        with m.db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM events WHERE delivered IS NOT NULL').fetchone()[0], 6)
            self.assertNotIn('private-sender-key', c.execute('SELECT webhook FROM bots LIMIT 1').fetchone()[0])

    def test_webhook_retry_restart(self):
        self.configure(self.server([503, 200]))
        with m.db() as c:
            m.event(c, {'id': 'task', 'bot': 'bot'}, 'failed', 'secret')
        self.assertTrue(m.deliver_alerts())
        m.deliver_alerts()
        self.assertEqual(len(self.requests), 1)  # Backoff persisted.
        with m.db() as c:
            row = c.execute('SELECT * FROM events').fetchone()
            self.assertEqual(row['attempts'], 1)
            self.assertIsNone(row['delivered'])
            c.execute('UPDATE events SET next_attempt=0')
        subprocess.run([sys.executable, '-c',
                        'import connector; connector.deliver_alerts()'],
                       cwd=m.ROOT, check=True)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0][1]['Idempotency-Key'], self.requests[1][1]['Idempotency-Key'])
        m.deliver_alerts()
        self.assertEqual(len(self.requests), 2)

    def test_acknowledged_and_pre_registration_events_are_not_sent(self):
        url = self.server()
        with m.db() as c:
            c.execute("INSERT INTO bots(id) VALUES('bot')")
            m.event(c, {'id': 'old', 'bot': 'bot'}, 'failed', 'old')
        self.configure(url)
        with m.db() as c:
            m.event(c, {'id': 'acked', 'bot': 'bot'}, 'stalled', 'acked')
            c.execute("UPDATE events SET acknowledged=1 WHERE task='acked'")
            m.event(c, {'id': 'new', 'bot': 'bot'}, 'cancelled', 'new')
        self.assertFalse(m.deliver_alerts())
        m.deliver_alerts()
        self.assertEqual([r[2]['task_id'] for r in self.requests], ['new'])

    def test_acknowledgement_stops_failed_delivery_retries(self):
        self.configure(self.server([503]))
        with m.db() as c:
            m.event(c, {'id': 'acked', 'bot': 'bot'}, 'failed', 'failed')
        self.assertTrue(m.deliver_alerts())
        with m.db() as c:
            c.execute('UPDATE events SET acknowledged=1,next_attempt=0')
        self.assertFalse(m.deliver_alerts())
        self.assertEqual(len(self.requests), 1)

    def test_legacy_webhook_migration_does_not_replay_history(self):
        self.configure(self.server())
        with m.db() as c:
            m.event(c, {'id': 'old', 'bot': 'bot'}, 'failed', 'old')
            c.execute('UPDATE bots SET webhook_registered=NULL')
        self.assertFalse(m.deliver_alerts())
        self.assertEqual(self.requests, [])

    def test_terminal_workers_post_once(self):
        self.configure(self.server())
        cases = [('failed', 'FAIL_TEST', {}),
                 ('timed_out', 'SLOW_TEST', dict(timeout_seconds=1.2, idle_seconds=1)),
                 ('stalled', 'SILENT_TEST', dict(idle_seconds=1, timeout_seconds=5)),
                 ('cancelled', 'SILENT_TEST', {})]
        for expected, prompt, options in cases:
            with self.subTest(kind=expected):
                task = self.start(prompt, **options)
                if expected == 'cancelled':
                    m.call('cancel_task', {'task_id': task['id']})
                self.assertEqual(self.finish(task)['status'], expected)
                deadline = time.monotonic() + 5
                while not any(r[2]['task_id'] == task['id'] for r in self.requests):
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.1)
                time.sleep(1.2)  # Let the worker sender finish before checking retries.
                m.deliver_alerts()
                posts = [r[2] for r in self.requests if r[2]['task_id'] == task['id']]
                self.assertEqual([p['kind'] for p in posts], [expected])
        self.assertEqual(len(self.requests), 4)

    def test_concurrent_delivery_and_cancel_deduplication(self):
        self.configure(self.server())
        with m.db() as c:
            for _ in range(2):
                m.event(c, {'id': 'task', 'bot': 'bot'}, 'cancelled', 'cancel')
        threads = [threading.Thread(target=m.deliver_alerts) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        m.deliver_alerts()
        self.assertEqual(len(self.requests), 1)

    def test_redirect_does_not_forward_key(self):
        self.configure(self.server([302]))
        with m.db() as c:
            m.event(c, {'id': 'task', 'bot': 'bot'}, 'completed', 'ok')
        self.assertTrue(m.deliver_alerts())
        with m.db() as c:
            self.assertIsNone(c.execute('SELECT delivered FROM events').fetchone()[0])

    def test_key_file_and_custom_header(self):
        key = self.root / 'sender.key'
        key.write_text('file-secret')
        key.chmod(0o600)
        args = dict(bot_id='bot', url=self.server(), key_file=str(key), header='X-Sender-Key', prefix='')
        m.call('set_bot_webhook', args)
        with m.db() as c:
            m.event(c, {'id': 'task', 'bot': 'bot'}, 'completed', 'ok')
        m.deliver_alerts()
        self.assertEqual(self.requests[0][1]['X-Sender-Key'], 'file-secret')
        key.chmod(0o644)
        with self.assertRaises(ValueError):
            m.call('set_bot_webhook', args)
        with self.assertRaises(ValueError):
            m.call('set_bot_webhook', dict(args, key_env='TEST_SENDER_KEY'))

    def test_worker_wakes_without_bot_checks(self):
        self.configure(self.server())
        task = self.start('SILENT_TEST', idle_seconds=1, timeout_seconds=5)
        deadline = time.monotonic() + 10
        while not self.requests and time.monotonic() < deadline:
            time.sleep(.1)  # Observe only the fake receiver, never query task status.
        self.assertEqual([r[2]['kind'] for r in self.requests], ['stalled'])
        self.assertEqual(self.requests[0][2]['task_id'], task['id'])
        time.sleep(1.2)  # Allow detached worker delivery thread to exit before cleanup.

    def test_secret_store_never_exposes_key(self):
        url = self.server()
        result = m.store_webhook('bot', url + '/hook', 'stored-secret-key')
        self.assertEqual(result, {'bot_id': 'bot', 'webhook_configured': True})
        path = m.key_path('bot')
        self.assertEqual(oct(path.stat().st_mode & 0o777), '0o600')
        self.assertEqual(oct(path.parent.stat().st_mode & 0o777), '0o700')
        with m.db() as c:
            self.assertNotIn('stored-secret-key', c.execute('SELECT webhook FROM bots').fetchone()[0])
            m.event(c, {'id': 'task', 'bot': 'bot'}, 'completed', 'ok')
        m.deliver_alerts()
        self.assertEqual(self.requests[0][1]['Authorization'], 'Bearer stored-secret-key')
        self.assertNotIn('stored-secret-key', json.dumps(m.doctor('bot')))
        with self.assertRaises(ValueError):
            m.store_webhook('bot2', 'http://example.com/insecure', 'k')
        self.assertFalse(m.key_path('bot2').exists())

    def test_webhook_form_single_use_loopback(self):
        import urllib.request, urllib.parse
        receiver = self.server()
        p = subprocess.Popen([sys.executable, str(m.ROOT / 'connector.py'), 'webhook-form', 'bot'],
                             stdout=subprocess.PIPE, text=True)
        try:
            info = json.loads(p.stdout.readline())
            self.assertTrue(info['form_url'].startswith('http://127.0.0.1:'))
            page = urllib.request.urlopen(info['form_url']).read().decode()
            self.assertIn('id="webhook_key"', page)
            bad = info['form_url'].rsplit('/', 1)[0] + '/wrong'
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(bad)
            body = urllib.parse.urlencode({'webhook_url': receiver + '/hook', 'webhook_key': 'form-secret'}).encode()
            reply = urllib.request.urlopen(info['form_url'], data=body).read().decode()
            self.assertIn('Saved', reply)
            self.assertNotIn('form-secret', reply)
            out = p.communicate(timeout=10)[0]
            self.assertEqual(json.loads(out), {'bot_id': 'bot', 'webhook_configured': True})
            self.assertNotIn('form-secret', out)
        finally:
            if p.poll() is None:
                p.kill()
        self.assertTrue(m.webhook_status('bot')['webhook_configured'])

    def test_mcp_wire(self):
        requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
                    {'jsonrpc':'2.0','method':'notifications/initialized'},
                    {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                    {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'model_choices'}}]
        p = subprocess.run([sys.executable, str(m.ROOT/'connector.py'), 'mcp'], input=''.join(json.dumps(r)+'\n' for r in requests), text=True, capture_output=True, check=True)
        answers = [json.loads(line) for line in p.stdout.splitlines()]
        self.assertEqual(len(answers), 3)
        self.assertEqual(len(answers[1]['result']['tools']), 11)
        self.assertIn('options', json.loads(answers[2]['result']['content'][0]['text']))

if __name__ == '__main__': unittest.main()
