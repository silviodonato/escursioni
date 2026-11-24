import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import activity_metrics as metrics
import genera_indice as generator


class MetricsChecks(unittest.TestCase):
    def test_constant_speed_and_interpolated_end(self):
        points = [(0, 0, 0), (0, .006, 60), (0, .012, 120)]
        result = metrics.best_effort(points, 1000)
        self.assertAlmostEqual(result['seconds'], 1000/metrics.hav(points[0], points[1])*60, places=3)
        self.assertIsNone(metrics.best_effort(points, 5000))

    def test_start_anchored_candidate_can_be_best(self):
        # Slow, fast, slow: the optimal end falls between recorded points.
        points = [(0, 0, 0), (0, .01, 1000), (0, .02, 1100), (0, .03, 2100)]
        result = metrics.best_effort(points, 1000)
        self.assertAlmostEqual(result['seconds'], 89.932, places=3)

    def test_stops_inside_effort_are_included(self):
        points = [(0, 0, 0), (0, .005, 50), (0, .005, 100), (0, .01, 150)]
        self.assertGreater(metrics.best_effort(points, 1000)['seconds'], 139)

    def test_sport_formats_and_segment_breaks(self):
        def point(lon, time):
            return '<trkpt lat="0" lon="{}"><time>2026-01-01T00:{}:00Z</time></trkpt>'.format(lon, time)
        text = '<gpx><trk><trkseg>'+point(0, '00')+point(.005, '01')+'</trkseg><trkseg>'+point(.005, '02')+point(.01, '03')+'</trkseg></trk></gpx>'
        self.assertEqual(metrics.analyze(text, 'GPX')['efforts'], {})
        tcx = '<TrainingCenterDatabase><Activities><Activity><Lap><Track>'+''.join('<Trackpoint><Time>2026-01-01T00:0{}:00Z</Time><Position><LatitudeDegrees>0</LatitudeDegrees><LongitudeDegrees>{}</LongitudeDegrees></Position></Trackpoint>'.format(i, i*.006) for i in range(3))+'</Track></Lap></Activity></Activities></TrainingCenterDatabase>'
        self.assertIn('1000', metrics.analyze(tcx, 'TCX')['efforts'])

    def test_gaps_missing_time_and_jumps_do_not_create_records(self):
        text = '<gpx><trk><trkseg><trkpt lat="0" lon="0"><time>2026-01-01T00:00:00Z</time></trkpt><trkpt lat="0" lon="1"><time>2026-01-01T00:00:01Z</time></trkpt><trkpt lat="0" lon="1.01"/><trkpt lat="0" lon="1.02"><time>2026-01-01T00:10:00Z</time></trkpt><trkpt lat="0" lon="1.04"><time>2026-01-01T01:00:00Z</time></trkpt></trkseg></trk></gpx>'
        result = metrics.analyze(text, 'GPX')
        self.assertEqual(result['efforts'], {})
        self.assertEqual(result['quality']['gps_jumps'], 1)
        self.assertEqual(result['quality']['gaps'], 1)
        self.assertEqual(result['quality']['missing_time'], 1)
        self.assertIsNone(metrics.stamp('2026-01-01T00:00:00'))

    def test_broken_extensions_are_flagged_and_cached(self):
        from verify_incremental import gpx
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tracks=root/'tracce';tracks.mkdir()
            text=gpx().replace('</trkseg>','<unknown:extension/></trkseg>')
            (tracks/'first.gpx').write_text(text)
            with patch.multiple(generator,HERE=str(root),TRACCE=str(tracks),OUT=str(tracks/'index.json')):
                self.assertEqual(generator.main()['errors'],1)
                entry=json.loads((tracks/'index.json').read_text())[0]
                self.assertEqual(entry['quality'],{'xml_error':1})
                self.assertGreater(entry['km'],0)
                with patch.object(generator,'read_snapshot',side_effect=AssertionError('Repeated failed read')):
                    self.assertEqual(generator.main()['errors'],0)

    def test_cache_upgrade_keeps_existing_statistics(self):
        from verify_incremental import gpx
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); tracks = root/'tracce'; tracks.mkdir()
            (tracks/'first.gpx').write_text(gpx())
            with patch.multiple(generator, HERE=str(root), TRACCE=str(tracks), OUT=str(tracks/'index.json')):
                generator.main()
                entries=json.loads((tracks/'index.json').read_text())
                entries[0].pop('_insights_version');entries[0]['gain']=12345
                (tracks/'index.json').write_text(json.dumps(entries))
                with patch.object(generator, 'parse', side_effect=AssertionError('Recalculated old statistics')):
                    result=generator.main(max_files=1)
                self.assertEqual(result['processed'], 0)
                self.assertEqual(json.loads((tracks/'index.json').read_text())[0]['gain'], 12345)
                with patch.object(generator, 'read_snapshot', side_effect=AssertionError('Re-read cached file')):
                    self.assertFalse(generator.main()['written'])


if __name__ == '__main__': unittest.main()
