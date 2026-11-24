import json,unittest,tempfile
from pathlib import Path
import genera_indice as g
class Formats(unittest.TestCase):
 def tcx(self,points=True):
  track='<Track><Trackpoint><Time>2026-01-01T10:00:00Z</Time><Position><LatitudeDegrees>44</LatitudeDegrees><LongitudeDegrees>9</LongitudeDegrees></Position></Trackpoint><Trackpoint><Time>2026-01-01T10:10:00Z</Time><Position><LatitudeDegrees>44.01</LatitudeDegrees><LongitudeDegrees>9.01</LongitudeDegrees></Position></Trackpoint></Track>' if points else ''
  return '  <?xml version="1.0"?><TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Activities><Activity Sport="Biking"><Id>2026-01-01T10:00:00Z</Id><Lap><TotalTimeSeconds>600</TotalTimeSeconds><DistanceMeters>2000</DistanceMeters>'+track+'</Lap></Activity></Activities></TrainingCenterDatabase>'
 def test_namespace_tcx(self):
  e=g.parse('a.tcx',self.tcx());self.assertEqual(e['format'],'TCX');self.assertTrue(e['has_gps']);self.assertEqual(e['dur_s'],600);self.assertGreater(e['km'],1);self.assertEqual(len(e['routes']),1)
 def test_indoor_tcx(self):
  e=g.parse('a.tcx',self.tcx(False));self.assertFalse(e['has_gps']);self.assertEqual(e['km'],2);self.assertEqual(e['dur_s'],600)
 def test_reject_entity(self):
  with self.assertRaises(ValueError):g.parse('a.tcx','<!DOCTYPE x>'+self.tcx())
 def test_geometry_keeps_segments(self):
  m=g.route_metadata([[(44,9),(44.01,9)],[(45,10),(45.01,10)]]);self.assertEqual(len(m['routes']),2);self.assertEqual(m['bounds'],[44,9,45.01,10])
 def test_simplification_keeps_turn(self):
  p=[(44,9),(44.01,9),(44.01,9.01)];self.assertEqual(len(g.simplify_route(p)),3)
 def test_cached_tcx_and_bad_xml(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'one.tcx').write_text(self.tcx());(root/'bad.tcx').write_text('<bad>')
   with patch.multiple(g,TRACCE=directory,OUT=str(root/'index.json')):
    first=g.main();self.assertEqual(first['processed'],1);self.assertEqual(first['errors'],1)
    with patch.object(g,'parse',wraps=g.parse) as parser:
     self.assertEqual(g.main()['reused'],1);self.assertEqual(parser.call_count,1)
if __name__=='__main__':unittest.main(verbosity=2)
