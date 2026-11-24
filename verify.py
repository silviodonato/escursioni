import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import ipaddress
import activity_config
activity_config.OWNER='testowner'
activity_config.HOSTS=('nas.test',)
activity_config.NETWORKS=(ipaddress.ip_network('192.168.1.0/24'),)
import subprocess
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('handler', str(Path(__file__).with_name('aggiorna_indice.cgi')))
spec = importlib.util.spec_from_loader(loader.name, loader)
handler = importlib.util.module_from_spec(spec)
loader.exec_module(handler)
handler.OWNER='testowner';handler.HOSTS=('nas.test',);handler.NETWORKS=activity_config.NETWORKS

ENV = {'REQUEST_METHOD': 'POST', 'HTTP_HOST': 'nas.test',
       'HTTP_ORIGIN': 'http://nas.test', 'HTTP_X_ESCURSIONI_ACTION': 'update-index',
       'REMOTE_ADDR': '192.168.1.42'}


def request(env, authenticated=False):
    output = io.StringIO()
    with patch.dict(os.environ, env, clear=True), patch.object(handler, 'authenticated_owner', return_value=authenticated), patch.object(handler, 'regenerate') as run, contextlib.redirect_stdout(output):
        handler.main()
        return output.getvalue(), run.called


class Checks(unittest.TestCase):
    def test_no_execution_without_login(self):
        output, called = request(ENV)
        self.assertIn('401 Unauthorized', output)
        self.assertFalse(called)

    def test_no_get_execution(self):
        output, called = request(dict(ENV, REQUEST_METHOD='GET'), True)
        self.assertIn('405 Method Not Allowed', output)
        self.assertFalse(called)

    def test_no_cross_site_execution(self):
        for origin in ('http://other.example', 'null', '', 'http://nas.test.evil.example'):
            output, called = request(dict(ENV, HTTP_ORIGIN=origin), True)
            self.assertIn('403 Forbidden', output)
            self.assertFalse(called)

    def test_no_foreign_host_execution(self):
        output, called = request(dict(ENV, HTTP_HOST='other.example', HTTP_ORIGIN='http://other.example'), True)
        self.assertIn('403 Forbidden', output)
        self.assertFalse(called)

    def test_no_simple_form_execution(self):
        env = dict(ENV)
        del env['HTTP_X_ESCURSIONI_ACTION']
        output, called = request(env, True)
        self.assertIn('403 Forbidden', output)
        self.assertFalse(called)

    def test_only_owner_allowed(self):
        for username, code in ((b'testowner\n', 0), (b'other\n', 0), (b'', 5), (b'testowner', 5)):
            result = subprocess.CompletedProcess([], code, stdout=username)
            with patch.dict(os.environ, {'HTTP_COOKIE': 'id=test-session'}, clear=True), patch.object(handler.subprocess, 'run', return_value=result):
                self.assertEqual(handler.authenticated_owner(), username.strip() == b'testowner' and code == 0)

    def test_missing_cookie_does_not_start_authenticator(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(handler.subprocess, 'run') as run:
            self.assertFalse(handler.authenticated_owner())
            run.assert_not_called()

    def test_public_and_proxy_sources_blocked_even_with_login(self):
        for address in ('100.100.100.100', '1.2.3.4', '', '192.168.2.42'):
            output, called = request(dict(ENV, REMOTE_ADDR=address), True)
            self.assertIn('403 Forbidden', output)
            self.assertFalse(called)

    def test_forwarded_requests_blocked_even_with_spoofed_lan_address(self):
        for header in ('HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_HOST', 'HTTP_FORWARDED'):
            output, called = request(dict(ENV, **{header: '192.168.1.42'}), True)
            self.assertIn('403 Forbidden', output)
            self.assertFalse(called)

    def test_local_loopback_still_requires_login(self):
        for address in ('127.0.0.1', '::1'):
            output, called = request(dict(ENV, REMOTE_ADDR=address))
            self.assertIn('401 Unauthorized', output)
            self.assertFalse(called)

    def test_forwarded_loopback_blocked_with_login(self):
        output, called = request(dict(ENV, REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='192.168.1.42'), True)
        self.assertIn('403 Forbidden', output)
        self.assertFalse(called)

    def test_authenticated_request_reaches_generator(self):
        output, called = request(ENV, True)
        self.assertTrue(called)

    def test_generator_is_fixed_and_returns_actual_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tracce').mkdir()
            (root / 'genera_indice.py').write_text("from pathlib import Path\nimport json\nPath('tracce/index.json').write_text('[{},{}]')\nprint(json.dumps(dict(processed=2,reused=0,removed=0,errors=0,written=True)))\n")
            output = io.StringIO()
            with patch.object(handler, 'HERE', root), contextlib.redirect_stdout(output):
                handler.regenerate()
            self.assertIn('200 OK', output.getvalue())
            self.assertEqual(json.loads(output.getvalue().split('\n\n', 1)[1])['count'], 2)
            key = handler.hashlib.sha256(str(root).encode()).hexdigest()[:16]
            Path(tempfile.gettempdir(), 'escursioni-{}-{}.lock'.format(os.getuid(), key)).unlink()


if __name__ == '__main__':
    unittest.main(verbosity=2)
