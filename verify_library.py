import unittest,tempfile,json,io,os,contextlib,importlib.util,importlib.machinery
from pathlib import Path
import ipaddress
import activity_config
activity_config.OWNER='testowner'
activity_config.HOSTS=('nas.test',)
activity_config.NETWORKS=(ipaddress.ip_network('192.168.1.0/24'),)
from unittest.mock import patch
import activity_store as store
import genera_indice as g
loader=importlib.machinery.SourceFileLoader('management',str(Path(__file__).with_name('gestisci_attivita.cgi')))
spec=importlib.util.spec_from_loader(loader.name,loader);api=importlib.util.module_from_spec(spec);loader.exec_module(api)
api.auth.OWNER='testowner';api.auth.HOSTS=('nas.test',);api.auth.NETWORKS=activity_config.NETWORKS
GPX='<gpx><trk><name>Original</name><trkseg><trkpt lat="44" lon="9"><time>2026-01-01T10:00:00Z</time></trkpt><trkpt lat="44.01" lon="9.01"><time>2026-01-01T10:10:00Z</time></trkpt></trkseg></trk></gpx>'
class Management(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.tracks=self.root/'tracce';self.tracks.mkdir();self.state=self.root/'private';(self.state/'trash').mkdir(parents=True)
  self.patches=[patch.object(store,'STATE',self.state),patch.multiple(g,HERE=str(self.root),TRACCE=str(self.tracks),OUT=str(self.tracks/'index.json'))]
  for p in self.patches:p.start()
  (self.tracks/'route.gpx').write_text(GPX);(self.tracks/'route.fit').write_bytes(b'original FIT')
  g.main();original_write=g.write_index
  self.writer=patch.object(g,'write_index',side_effect=lambda entries,web_acl=False:original_write(entries,False));self.writer.start()
 def tearDown(self):
  self.writer.stop()
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def test_rename_is_persistent_and_keeps_files(self):
  before=(self.tracks/'route.gpx').read_bytes();store.edit(g,'route.gpx','Monte & mare','hiking');g.main();entry=store.index(g)[0]
  self.assertEqual(entry['display_name'],'Monte & mare');self.assertEqual(entry['kind'],'hiking');self.assertEqual(entry['name'],'Original');self.assertEqual((self.tracks/'route.gpx').read_bytes(),before)
 def test_delete_bundle_and_restore_exact_bytes(self):
  store.edit(g,'route.gpx','Edited','walking');before={n:(self.tracks/n).read_bytes() for n in ['route.gpx','route.fit']}
  result=store.trash(g,'route.gpx');self.assertEqual(result['files'],2);self.assertEqual(store.index(g),[]);self.assertFalse((self.tracks/'route.fit').exists());self.assertEqual(len(store.trash_items()),1)
  self.assertEqual(g.main()['count'],0);store.restore(g,result['id'])
  for n,raw in before.items():self.assertEqual((self.tracks/n).read_bytes(),raw)
  self.assertEqual(store.index(g)[0]['display_name'],'Edited');self.assertEqual(g.main()['processed'],0);self.assertEqual(store.trash_items(),[])
 def test_restore_never_overwrites(self):
  result=store.trash(g,'route.gpx');(self.tracks/'route.fit').write_bytes(b'new FIT')
  with self.assertRaises(store.Conflict):store.restore(g,result['id'])
  self.assertEqual((self.tracks/'route.fit').read_bytes(),b'new FIT');self.assertFalse((self.tracks/'route.gpx').exists());self.assertEqual(len(store.trash_items()),1)
 def test_reject_path_traversal(self):
  for name in ['../route.gpx','/route.gpx','a\\route.gpx','x.php','\x00.gpx']:
   with self.assertRaises(ValueError):store.trash(g,name)
 def test_reject_symlink(self):
  (self.tracks/'route.gpx').unlink();(self.tracks/'route.gpx').symlink_to(self.tracks/'route.fit')
  with self.assertRaises(ValueError):store.trash(g,'route.gpx')
 def test_unknown_activity_cannot_be_removed(self):
  (self.tracks/'outside.gpx').write_text(GPX)
  with self.assertRaises(store.Conflict):store.trash(g,'outside.gpx')
 def test_bad_edit_does_not_write(self):
  for name,kind in [('', 'walking'),('x'*161,'walking'),('Name','unknown'),('A\nB','walking')]:
   with self.assertRaises(ValueError):store.edit(g,'route.gpx',name,kind)
  self.assertFalse((self.state/'metadata.json').exists())
 def test_index_failure_rolls_back_delete(self):
  with patch.object(g,'write_index',side_effect=OSError('disk full')):
   with self.assertRaises(OSError):store.trash(g,'route.gpx')
  self.assertTrue((self.tracks/'route.gpx').exists());self.assertTrue((self.tracks/'route.fit').exists());self.assertEqual(store.trash_items(),[])
 def test_shared_lock_conflict(self):
  with store.site_lock(self.root):
   with self.assertRaises(store.Conflict):
    with store.site_lock(self.root):pass
 def request(self,env,logged=False,body='{}'):
  out=io.StringIO()
  with patch.dict(os.environ,env,clear=True),patch.object(api.auth,'authenticated_owner',return_value=logged),patch.object(api.sys,'stdin',io.StringIO(body)),patch.object(store,'trash') as trash,contextlib.redirect_stdout(out):api.main()
  return out.getvalue(),trash.called
 def env(self):return dict(REQUEST_METHOD='POST',HTTP_HOST='nas.test',HTTP_ORIGIN='http://nas.test',HTTP_X_ESCURSIONI_ACTION='manage-activity',REMOTE_ADDR='192.168.1.42',CONTENT_TYPE='application/json',CONTENT_LENGTH='2')
 def test_anonymous_cannot_manage(self):
  result,called=self.request(self.env());self.assertIn('401 Unauthorized',result);self.assertFalse(called)
 def test_public_and_forged_sources_blocked(self):
  for changes in [dict(HTTP_HOST='public.example.test',HTTP_ORIGIN='https://public.example.test'),dict(HTTP_X_FORWARDED_FOR='192.168.1.42'),dict(HTTP_ORIGIN='http://evil.test'),dict(REMOTE_ADDR='8.8.8.8'),dict(HTTP_X_ESCURSIONI_ACTION='update-index')]:
   result,called=self.request(dict(self.env(),**changes),True);self.assertIn('403 Forbidden',result);self.assertFalse(called)
 def test_get_cannot_manage(self):
  result,called=self.request(dict(self.env(),REQUEST_METHOD='GET'),True);self.assertIn('405 Method Not Allowed',result);self.assertFalse(called)
 def test_unexpected_action_rejected(self):
  result,called=self.request(dict(self.env(),CONTENT_LENGTH='19'),True,'{"action":"shell"}');self.assertIn('400 Bad Request',result);self.assertFalse(called)
if __name__=='__main__':unittest.main(verbosity=2)
