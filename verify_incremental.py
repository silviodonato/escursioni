import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('generator', Path(__file__).with_name('genera_indice.py'))
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def gpx(latitude='44.1000', name='Test route'):
    return ('<gpx><trk><name>'+name+'</name><trkseg>'
            '<trkpt lat="'+latitude+'" lon="9.1000"><ele>10</ele><time>2026-11-01T10:00:00Z</time></trkpt>'
            '<trkpt lat="44.2000" lon="9.2000"><ele>20</ele><time>2026-11-01T10:10:00Z</time></trkpt>'
            '</trkseg></trk></gpx>')


class IncrementalChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.tracks = self.root / 'tracce'
        self.tracks.mkdir()
        self.patcher = patch.multiple(generator, HERE=str(self.root), TRACCE=str(self.tracks), OUT=str(self.tracks/'index.json'))
        self.patcher.start()
        self.first = self.tracks/'first.gpx'
        self.first.write_text(gpx())

    def tearDown(self):
        self.patcher.stop()
        self.temporary.cleanup()

    def test_repeat_does_not_read_parse_or_write(self):
        self.assertEqual(generator.main()['processed'], 1)
        before = (self.tracks/'index.json').stat().st_mtime_ns
        with patch.object(generator, 'read_snapshot', side_effect=AssertionError('GPX read')), patch.object(generator, 'parse', side_effect=AssertionError('GPX parse')), patch.object(generator, 'write_index', side_effect=AssertionError('Index write')):
            result = generator.main(web_acl=True)
        self.assertEqual(result, dict(count=1, processed=0, reused=1, removed=0, errors=0, written=False, pending=0))
        self.assertEqual((self.tracks/'index.json').stat().st_mtime_ns, before)
        self.assertFalse((self.tracks/'index.json.tmp').exists())

    def test_only_new_file_is_parsed(self):
        generator.main()
        (self.tracks/'new.GPX').write_text(gpx(name='New route'))
        with patch.object(generator, 'parse', wraps=generator.parse) as parse:
            result = generator.main()
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['reused'], 1)
        self.assertEqual(Path(parse.call_args.args[0]).name, 'new.GPX')

    def test_changed_size_with_preserved_mtime_is_detected(self):
        generator.main()
        old = self.first.stat()
        self.first.write_text(gpx(name='Changed route with a longer name'))
        os.utime(self.first, ns=(old.st_atime_ns, old.st_mtime_ns))
        result = generator.main()
        self.assertEqual(result['processed'], 1)
        entries = json.loads((self.tracks/'index.json').read_text())
        self.assertEqual(entries[0]['name'], 'Changed route with a longer name')

    def test_subsecond_edit_is_detected(self):
        generator.main()
        old = self.first.stat()
        self.first.write_text(gpx(latitude='44.3000'))
        base = (old.st_mtime_ns // 1_000_000_000) * 1_000_000_000
        os.utime(self.first, ns=(old.st_atime_ns, base+1))
        self.assertEqual(generator.main()['processed'], 1)

    def test_touch_does_not_reparse_identical_content(self):
        generator.main()
        old = self.first.stat()
        os.utime(self.first, ns=(old.st_atime_ns, old.st_mtime_ns+1_000_000))
        with patch.object(generator, 'parse', side_effect=AssertionError('Unnecessary parse')):
            result = generator.main()
        self.assertEqual(result['processed'], 0)
        self.assertEqual(result['reused'], 1)
        self.assertEqual(generator.main()['written'], False)

    def test_same_size_and_mtime_edit_detected_by_ctime(self):
        generator.main()
        old = self.first.stat()
        # Older DSM kernels timestamp ctime on clock ticks, unlike the local host.
        time.sleep(0.05)
        self.first.write_text(gpx(latitude='44.3000'))
        os.utime(self.first, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.assertNotEqual(self.first.stat().st_ctime_ns, old.st_ctime_ns)
        self.assertEqual(generator.main()['processed'], 1)

    def test_removed_file_needs_no_reparsing(self):
        generator.main()
        self.first.unlink()
        with patch.object(generator, 'parse', side_effect=AssertionError('Unexpected parse')):
            result = generator.main()
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['removed'], 1)
        self.assertEqual(result['processed'], 0)
        self.assertEqual(json.loads((self.tracks/'index.json').read_text()), [])

    def test_version_one_geometry_upgrade_reuses_statistics(self):
        generator.main()
        path=self.tracks/'index.json'
        old=json.loads(path.read_text());old[0]['_cache_version']=1
        for key in ['routes','bounds','has_gps','route_tolerance_m','format','sport']:
            old[0].pop(key,None)
        path.write_text(json.dumps(old))
        with patch.object(generator,'parse',side_effect=AssertionError('Statistics should be reused')):
            result=generator.main()
        self.assertEqual(result['processed'],0)
        upgraded=json.loads(path.read_text())[0]
        self.assertTrue(upgraded['routes'])
        self.assertEqual(upgraded['km'],old[0]['km'])
        self.assertEqual(upgraded['_cache_version'],generator.CACHE_VERSION)

    def test_metadata_changes_write_without_reparsing(self):
        generator.main()
        def new_label(entries):
            for entry in entries:entry['display_name']='New label'
            return entries
        with patch.object(generator,'decorate',side_effect=new_label),patch.object(generator,'parse',side_effect=AssertionError('Unnecessary parse')):
            self.assertTrue(generator.main()['written'])
            self.assertFalse(generator.main()['written'])
        self.assertEqual(json.loads((self.tracks/'index.json').read_text())[0]['display_name'],'New label')

    def test_old_index_is_upgraded_once(self):
        old = generator.parse(str(self.first))
        old.update(file='first.gpx', mtime=int(self.first.stat().st_mtime), size=self.first.stat().st_size)
        (self.tracks/'index.json').write_text(json.dumps([old]))
        self.assertEqual(generator.main()['processed'], 1)
        self.assertEqual(generator.main()['processed'], 0)

    def test_saved_batches_resume_without_reparsing(self):
        (self.tracks/'second.gpx').write_text(gpx(name='Second route'))
        (self.tracks/'third.gpx').write_text(gpx(name='Third route'))
        parsed=[]
        original=generator.parse
        def record(path, text):
            parsed.append(Path(path).name)
            return original(path, text)
        with patch.object(generator, 'parse', side_effect=record):
            first=generator.main(max_files=1)
            second=generator.main(max_files=1)
            third=generator.main(max_files=1)
            fourth=generator.main(max_files=1)
        self.assertEqual([first['pending'],second['pending'],third['pending'],fourth['pending']],[2,1,0,0])
        self.assertEqual(parsed,['first.gpx','second.gpx','third.gpx'])
        self.assertEqual(fourth['processed'],0)
        self.assertFalse(fourth['written'])

    def test_batch_keeps_previous_results_for_deferred_changed_files(self):
        second=self.tracks/'second.gpx'
        second.write_text(gpx(name='Second route'))
        generator.main()
        self.first.write_text(gpx(name='Changed first'))
        second.write_text(gpx(name='Changed second'))
        result=generator.main(max_files=1)
        names={e['file']:e['name'] for e in json.loads((self.tracks/'index.json').read_text())}
        self.assertEqual(result['pending'],1)
        self.assertEqual(names,{'first.gpx':'Changed first','second.gpx':'Second route'})
        self.assertEqual(generator.main(max_files=1)['pending'],0)

    def test_corrupt_index_is_rebuilt(self):
        (self.tracks/'index.json').write_text('broken JSON')
        self.assertEqual(generator.main()['processed'], 1)
        self.assertEqual(generator.main()['written'], False)

    def test_incomplete_upload_preserves_previous_result(self):
        generator.main()
        before = json.loads((self.tracks/'index.json').read_text())
        self.first.write_text('<gpx>incomplete upload')
        with contextlib.redirect_stderr(io.StringIO()):
            result = generator.main()
        self.assertEqual(result['errors'], 1)
        self.assertEqual(json.loads((self.tracks/'index.json').read_text()), before)
        self.first.write_text(gpx(name='Finished upload'))
        self.assertEqual(generator.main()['processed'], 1)

    def test_new_file_statistics_match_original_parser(self):
        original_spec = importlib.util.spec_from_file_location('original', Path(__file__).with_name('reference_parser.py'))
        original = importlib.util.module_from_spec(original_spec)
        original_spec.loader.exec_module(original)
        expected = original.parse(str(self.first))
        generator.main()
        actual = json.loads((self.tracks/'index.json').read_text())[0]
        self.assertEqual({key:actual[key] for key in expected}, expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
