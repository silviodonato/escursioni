"""Names and types from the activities.csv of a Strava export (synthetic data only)."""
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import activity_store as store
import genera_indice as g

ITALIAN = ['ID attività', 'Data dell’attività', 'Nome attività', 'Tipo attività', 'Descrizione dell’attività',
           'Tempo trascorso', 'Distanza', 'Frequenza cardiaca massima', 'Sforzo relativo', 'Tragitto pendolare',
           'Nota privata sulle attività', 'Attrezzatura attività', 'Nome del file', 'Tempo trascorso', 'Distanza']
GPX = ('<gpx><trk><name>Dal dispositivo</name><trkseg>'
       '<trkpt lat="44.1" lon="9.7"><time>2026-09-12T08:00:00Z</time></trkpt>'
       '<trkpt lat="44.11" lon="9.71"><time>2026-09-12T08:30:00Z</time></trkpt></trkseg></trk></gpx>')


def export(header, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


def italian_row(number, name, kind, extension='fit.gz', description=''):
    row = [''] * len(ITALIAN)
    row[0], row[2], row[3], row[4] = number, name, kind, description
    row[10], row[12] = 'nota privata', 'activities/{}.{}'.format(number, extension) if extension else ''
    return row


class Catalog(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / 'activities.csv'

    def tearDown(self):
        self.temporary.cleanup()

    def test_italian_export_with_multiline_description(self):
        self.path.write_text('﻿' + export(ITALIAN, [
            italian_row('111', 'Riomaggiore - Santerenzo', 'Kayak', description='riga 1\nriga 2, "citata"'),
            italian_row('222', 'Monte', 'Escursione', 'tcx.gz'),
            italian_row('', 'Manuale', 'Corsa', ''),
        ]), encoding='utf-8')
        catalog = store.strava_catalog(self.path)
        self.assertEqual(catalog, {'111': {'name': 'Riomaggiore - Santerenzo', 'type': 'Kayak'},
                                   '222': {'name': 'Monte', 'type': 'Escursione'}})
        self.assertNotIn('nota privata', json.dumps(catalog))

    def test_english_and_unknown_headers(self):
        self.path.write_text(export(['Activity Type', 'Filename', 'Activity Name'],
                                    [['Kayaking', 'activities/333.gpx', 'Lake']]), encoding='utf-8')
        self.assertEqual(store.strava_catalog(self.path), {'333': {'name': 'Lake', 'type': 'Kayaking'}})
        self.path.write_text(export(['x'] * 13, [italian_row('444', 'Posizionale', 'Corsa')]), encoding='utf-8')
        self.assertEqual(store.strava_catalog(self.path)['444']['type'], 'Corsa')

    def test_missing_or_invalid_file(self):
        self.assertEqual(store.strava_catalog(self.path), {})
        self.path.write_bytes(b'\xff\xfe\x00broken')
        self.assertEqual(store.strava_catalog(self.path), {})

    def test_precedence(self):
        entry = {'file': 'a.gpx', 'name': '', 'sport': 'running', 'strava': {'name': 'Strava', 'type': 'Kayak'}}
        store.decorate([entry], {})
        self.assertEqual((entry['display_name'], entry['kind']), ('Strava', 'kayaking'))
        store.decorate([entry], {'a.gpx': {'name': 'Mio', 'kind': 'walking'}})
        self.assertEqual((entry['display_name'], entry['kind']), ('Mio', 'walking'))
        entry['strava']['type'] = 'Sport acquatico'  # unknown type: the device sport decides
        store.decorate([entry], {})
        self.assertEqual(entry['kind'], 'running')


class GeneratorUsesStrava(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.tracks, self.state = root / 'tracce', root / 'private'
        self.tracks.mkdir()
        self.state.mkdir()
        self.patches = [patch.object(store, 'STATE', self.state),
                        patch.multiple(g, HERE=str(root), TRACCE=str(self.tracks), OUT=str(self.tracks / 'index.json'))]
        original = g.write_index  # no Synology ACL outside the NAS
        self.patches.append(patch.object(g, 'write_index', side_effect=lambda entries, web_acl=False: original(entries, False)))
        for active in self.patches:
            active.start()
        (self.tracks / '111.gpx').write_text(GPX)

    def tearDown(self):
        for active in reversed(self.patches):
            active.stop()
        self.temporary.cleanup()

    def entry(self):
        return json.loads((self.tracks / 'index.json').read_text())[0]

    def test_names_types_and_removal(self):
        g.main()
        self.assertEqual((self.entry().get('display_name'), self.entry()['kind']), (None, 'other'))
        csv_path = self.state / 'strava_activities.csv'
        csv_path.write_text(export(ITALIAN, [italian_row('111', 'Riomaggiore - Santerenzo', 'Kayak')]), encoding='utf-8')
        with patch.object(g, 'parse', side_effect=AssertionError('GPX parse')):
            self.assertTrue(g.main()['written'])
        self.assertEqual((self.entry()['display_name'], self.entry()['kind'], self.entry()['name']),
                         ('Riomaggiore - Santerenzo', 'kayaking', 'Dal dispositivo'))
        self.assertFalse(g.main()['written'])
        store.edit(g, '111.gpx', 'Nome mio', 'sup')
        self.assertEqual((self.entry()['display_name'], self.entry()['kind']), ('Nome mio', 'sup'))
        csv_path.unlink()
        (self.state / 'metadata.json').unlink()
        g.main()
        self.assertNotIn('strava', self.entry())
        self.assertEqual((self.entry().get('display_name'), self.entry()['kind']), (None, 'other'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
