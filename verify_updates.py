import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import activity_config
import website_update as u

loader = importlib.machinery.SourceFileLoader('site_update_api', str(Path(__file__).with_name('aggiorna_sito.cgi')))
spec = importlib.util.spec_from_loader(loader.name, loader)
api = importlib.util.module_from_spec(spec)
loader.exec_module(api)
SHA = 'a' * 40


def archive(extra=None, omit=None, invalid=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        for name in u.FILES:
            if name == omit:
                continue
            body = '<!doctype html><html></html>' if name.endswith('.html') else '# test\n' if name.endswith(('.py', '.cgi')) else '// test\n'
            if invalid and name == 'genera_indice.py':
                body = 'def broken(\n'
            z.writestr('repo-' + SHA + '/' + name, body)
        if extra:
            z.writestr(*extra)
    return output.getvalue()


class Updates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.patch = patch.multiple(u, STATE=self.base, SITE=self.base / 'site',
                                    SETTINGS={'repository': 'example/activities'})
        self.patch.start()
        (u.root() / 'releases').mkdir(parents=True)
        old = u.root() / 'releases' / 'initial'
        old.mkdir()
        hashes = u.unpack(archive(), old)
        (old / 'release.json').write_text(json.dumps({'sha': 'initial', 'files': hashes}))
        (u.root() / 'current').symlink_to(old)
        self.old = old

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def install(self, raw=None, **kwargs):
        with patch.object(u, 'candidate', return_value={'sha': SHA, 'title': 'Test'}), \
                patch.object(u, 'fetch', return_value=archive() if raw is None else raw), \
                patch.object(u.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0), **kwargs):
            return u.install(SHA)

    def test_success_and_round_trip_rollback_keep_data(self):
        (u.SITE / 'tracce').mkdir(parents=True)
        activity = u.SITE / 'tracce' / 'my.gpx'
        activity.write_bytes(b'private track')
        journal = self.base / 'journal.json'
        journal.write_text('private diary')
        result = self.install()
        self.assertEqual(result['current'], SHA)
        self.assertEqual(result['previous'], 'initial')
        self.assertEqual(u.rollback()['current'], 'initial')
        self.assertEqual(u.rollback()['current'], SHA)
        self.assertEqual(activity.read_bytes(), b'private track')
        self.assertEqual(journal.read_text(), 'private diary')

    def test_missing_file_bad_python_and_path_traversal_never_activate(self):
        for raw in [archive(omit='library.js'), archive(invalid=True),
                    archive(('repo-' + SHA + '/../evil.py', 'malicious')),
                    archive(('other-root/extra', 'x'))]:
            with self.assertRaises((u.UpdateError, SyntaxError)):
                self.install(raw)
            self.assertEqual(u.target('current'), self.old)
            self.assertEqual(list((u.root() / 'releases').iterdir()), [self.old])

    def test_duplicate_and_symlink_archive_rejected(self):
        with self.assertRaises(u.UpdateError):
            self.install(archive(('repo-' + SHA + '/index.html', '<!doctype html>')))
        stream = io.BytesIO(archive())
        with zipfile.ZipFile(stream, 'a') as z:
            entry = zipfile.ZipInfo('repo-' + SHA + '/symlink')
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(entry, '/etc/passwd')
        with self.assertRaises(u.UpdateError):
            self.install(stream.getvalue())

    def test_python_failure_keeps_original_version(self):
        with patch.object(u, 'candidate', return_value={'sha': SHA}), \
                patch.object(u, 'fetch', return_value=archive()), \
                patch.object(u.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaises(u.UpdateError):
                u.install(SHA)
        self.assertEqual(u.target('current'), self.old)

    def test_final_verification_failure_restores_original(self):
        verify = u.verify
        calls = []
        def fail_after_switch(folder):
            calls.append(folder)
            if len(calls) == 2:
                raise u.UpdateError('Simulated final check failure')
            return verify(folder)
        with patch.object(u, 'verify', side_effect=fail_after_switch):
            with self.assertRaises(u.UpdateError):
                self.install()
        self.assertEqual(u.target('current'), self.old)

    def test_tampered_backup_cannot_be_activated(self):
        self.install()
        (self.old / 'library.js').write_text('tampered')
        with self.assertRaises(u.UpdateError):
            u.rollback()
        self.assertEqual(u.version(u.target('current')), SHA)

    def test_moved_main_or_invalid_sha_does_not_download(self):
        with patch.object(u, 'candidate', return_value={'sha': 'b' * 40}), patch.object(u, 'fetch') as fetch:
            for sha in (SHA, '../main', None):
                with self.assertRaises(u.UpdateError):
                    u.install(sha)
            fetch.assert_not_called()

    def test_ci_must_be_successful_for_exact_main_commit_and_workflow(self):
        good = dict(head_sha=SHA, head_branch='main', event='push', path='.github/workflows/tests.yml',
                    run_number=1, status='completed', conclusion='success')
        for change in ({'head_sha': 'b' * 40}, {'head_branch': 'feature'}, {'event': 'pull_request'},
                       {'path': '.github/workflows/other.yml'}, {'conclusion': 'failure'}, {'status': 'in_progress'}):
            responses = [json.dumps({'sha': SHA}).encode(), json.dumps({'workflow_runs': [dict(good, **change)]}).encode()]
            with patch.object(u, 'fetch', side_effect=responses):
                with self.assertRaises(u.UpdateError):
                    u.candidate()
        responses = [json.dumps({'sha': SHA, 'commit': {'message': 'Test'}}).encode(), json.dumps({'workflow_runs': [good]}).encode()]
        with patch.object(u, 'fetch', side_effect=responses):
            self.assertEqual(u.candidate()['sha'], SHA)

    def test_api_blocks_anonymous_remote_get_cross_origin_and_arbitrary_parameters(self):
        env = dict(REQUEST_METHOD='POST', HTTP_HOST='nas.test', HTTP_ORIGIN='http://nas.test',
                   HTTP_X_ESCURSIONI_ACTION='update-site', REMOTE_ADDR='192.168.1.42', CONTENT_TYPE='application/json')
        for logged, changes, body in [(False, {}, '{"action":"install"}'),
                                      (True, {'REQUEST_METHOD': 'GET'}, '{}'),
                                      (True, {'REMOTE_ADDR': '8.8.8.8'}, '{}'),
                                      (True, {'HTTP_ORIGIN': 'http://evil.test'}, '{}'),
                                      (True, {'HTTP_X_FORWARDED_FOR': '192.168.1.42'}, '{}'),
                                      (True, {}, '{"action":"install","url":"https://evil.test"}')]:
            output = io.StringIO()
            with patch.dict(os.environ, dict(env, CONTENT_LENGTH=str(len(body)), **changes), clear=True), \
                    patch.object(api.guard, 'HOSTS', ('nas.test',)), \
                    patch.object(api.guard, 'NETWORKS', (__import__('ipaddress').ip_network('192.168.1.0/24'),)), \
                    patch.object(api.guard, 'authenticated_owner', return_value=logged), \
                    patch.object(api.sys, 'stdin', io.StringIO(body)), \
                    patch.object(u, 'install') as install, contextlib.redirect_stdout(output):
                api.main()
            install.assert_not_called()
            self.assertTrue('Forbidden' in output.getvalue() or 'Unauthorized' in output.getvalue() or
                            'Method Not Allowed' in output.getvalue() or '"error": true' in output.getvalue())

    def test_unconfigured_copy_has_no_management_hosts_or_owner(self):
        data = activity_config.load(self.base / 'nonexistent-config.json')
        self.assertEqual(data, {})


if __name__ == '__main__':
    unittest.main()
