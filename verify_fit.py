"""Sport of a GPX taken from the FIT original with the same name (synthetic data only)."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('generator_fit', Path(__file__).with_name('genera_indice.py'))
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def definition(local, number, fields, big=False, developer=()):
    header = 0x40 | local | (0x20 if developer else 0)
    body = bytes([0, 1 if big else 0]) + number.to_bytes(2, 'big' if big else 'little') + bytes([len(fields)])
    for num, size in fields:
        body += bytes([num, size, 0])
    if developer:
        body += bytes([len(developer)]) + b''.join(bytes([num, size, 0]) for num, size in developer)
    return bytes([header]) + body


def fit(*records):
    data = b''.join(records)
    return bytes([14, 0x20]) + (2147).to_bytes(2, 'little') + len(data).to_bytes(4, 'little') + b'.FIT\0\0' + data + b'\0\0'


def sport_file(sport=41, sub_sport=19):
    file_id = definition(0, 0, [(0, 1), (4, 4)]) + bytes([0, 4]) + (1).to_bytes(4, 'little')
    return fit(file_id, definition(1, 12, [(0, 1), (1, 1), (3, 16)]),
               bytes([1, sport, sub_sport]) + b'kayaking'.ljust(16, b'\0'))


def gpx():
    return ('<gpx><trk><trkseg>'
            '<trkpt lat="44.1000" lon="9.1000"><time>2026-10-04T10:00:00Z</time></trkpt>'
            '<trkpt lat="44.1100" lon="9.1100"><time>2026-10-04T10:30:00Z</time></trkpt>'
            '</trkseg></trk></gpx>')


class FitSport(unittest.TestCase):
    def test_sport_message(self):
        self.assertEqual(generator.fit_sport(sport_file()), 'kayaking')
        self.assertEqual(generator.fit_sport(sport_file(17, 26)), 'hiking')
        self.assertEqual(generator.fit_sport(sport_file(4, 15)), 'elliptical')
        self.assertIsNone(generator.fit_sport(sport_file(0, 0)))
        self.assertIsNone(generator.fit_sport(sport_file(25, 0)))

    def test_session_with_compressed_header_developer_fields_and_big_endian(self):
        record = definition(2, 20, [(253, 4), (0, 4)], developer=[(0, 2)])
        point = bytes([0x80 | (2 << 5) | 3]) + (5).to_bytes(4, 'little') + bytes(6)  # compressed timestamp
        session = definition(3, 18, [(5, 1), (6, 1), (7, 4)], big=True)
        data = fit(record, bytes([2]) + bytes(10), point, session, bytes([3, 1, 2]) + (600).to_bytes(4, 'big'))
        self.assertEqual(generator.fit_sport(data), 'running')

    def test_invalid_files(self):
        for data in (b'', b'<gpx/>', sport_file()[:-6], fit(bytes([5, 1, 2]))):
            with self.assertRaises(ValueError):
                generator.fit_sport(data)


class GeneratorUsesFit(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.tracks = Path(self.temporary.name) / 'tracce'
        self.tracks.mkdir()
        self.patcher = patch.multiple(generator, HERE=self.temporary.name, TRACCE=str(self.tracks),
                                      OUT=str(self.tracks / 'index.json'))
        self.patcher.start()
        (self.tracks / 'trip.gpx').write_text(gpx())
        (self.tracks / 'trip.FIT').write_bytes(sport_file())

    def tearDown(self):
        self.patcher.stop()
        self.temporary.cleanup()

    def entry(self):
        return json.loads((self.tracks / 'index.json').read_text())[0]

    def test_gpx_gets_sport_from_fit_and_cache_avoids_rereading(self):
        result = generator.main()
        self.assertEqual(result['count'], 1)
        self.assertEqual((self.entry()['sport'], self.entry()['kind']), ('kayaking', 'kayaking'))
        with patch.object(generator, 'fit_sport', side_effect=AssertionError('FIT read')), \
                patch.object(generator, 'write_index', side_effect=AssertionError('Index write')):
            self.assertFalse(generator.main()['written'])

    def test_changed_or_removed_fit(self):
        generator.main()
        fit_path = self.tracks / 'trip.FIT'
        fit_path.write_bytes(sport_file(1, 0) + b'\0')
        os.utime(fit_path, ns=(1, 1))
        self.assertTrue(generator.main()['written'])
        self.assertEqual(self.entry()['kind'], 'running')
        fit_path.unlink()
        self.assertTrue(generator.main()['written'])
        self.assertEqual((self.entry()['sport'], self.entry()['kind']), (None, 'other'))
        self.assertNotIn('_fit', self.entry())

    def test_unreadable_fit_does_not_block_index(self):
        (self.tracks / 'trip.FIT').write_bytes(b'not a fit file')
        result = generator.main()
        self.assertEqual((result['count'], result['errors']), (1, 0))
        self.assertEqual(self.entry()['kind'], 'other')
        with patch.object(generator, 'fit_sport', side_effect=AssertionError('FIT read')):
            generator.main()


if __name__ == '__main__':
    unittest.main(verbosity=2)
