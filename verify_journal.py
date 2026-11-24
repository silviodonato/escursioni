import json
import unittest
from unittest.mock import patch
import verify_library as fixture
import activity_store as store
import genera_indice as generator

class JournalChecks(unittest.TestCase):
    setUp=fixture.Management.setUp
    tearDown=fixture.Management.tearDown

    def test_private_annotation_never_enters_public_index(self):
        before=(self.tracks/'index.json').read_bytes()
        store.edit_journal(generator,'route.gpx',True,'Una nota privata 🌄',['Panorama','panorama','Amici'])
        record=store.journal()['route.gpx']
        self.assertTrue(record['favorite']);self.assertEqual(record['tags'],['Panorama','Amici'])
        self.assertEqual(record['notes'],'Una nota privata 🌄')
        self.assertEqual((self.tracks/'index.json').read_bytes(),before)
        generator.main()
        self.assertNotIn('nota privata',(self.tracks/'index.json').read_text())
        store.edit(generator,'route.gpx','Nuovo nome','hiking')
        self.assertEqual(store.journal()['route.gpx'],record)

    def test_trash_and_restore_retain_private_journal(self):
        store.edit_journal(generator,'route.gpx',True,'Ricordo',['Estate'])
        result=store.trash(generator,'route.gpx');store.restore(generator,result['id'])
        self.assertEqual(store.journal()['route.gpx']['notes'],'Ricordo')

    def test_invalid_annotation_is_rejected(self):
        for file,favorite,notes,tags in [('../route.gpx',True,'',[]),('missing.gpx',True,'',[]),('route.gpx','yes','',[]),('route.gpx',True,'x'*4001,[]),('route.gpx',False,'',['x']*13),('route.gpx',False,'',['x'*33]),('route.gpx',False,'\0',[])]:
            with self.assertRaises(ValueError):store.edit_journal(generator,file,favorite,notes,tags)
        self.assertFalse((self.state/'journal.json').exists())

    def test_authenticated_api_saves_and_returns_private_notes(self):
        body=json.dumps({'action':'journal_edit','file':'route.gpx','favorite':True,'notes':'Private API note','tags':['Test']})
        env=dict(fixture.Management.env(self),CONTENT_LENGTH=str(len(body)))
        result,_=fixture.Management.request(self,env,True,body)
        self.assertIn('200 OK',result)
        self.assertEqual(store.journal()['route.gpx']['notes'],'Private API note')
        body=json.dumps({'action':'status'})
        env=dict(fixture.Management.env(self),CONTENT_LENGTH=str(len(body)))
        result,_=fixture.Management.request(self,env,True,body)
        self.assertIn('Private API note',result)
        self.assertNotIn('Private API note',(self.tracks/'index.json').read_text())

    def test_empty_entry_is_removed(self):
        store.edit_journal(generator,'route.gpx',True,'Note',['Tag'])
        store.edit_journal(generator,'route.gpx',False,'',[])
        self.assertEqual(store.journal(),{})

    def test_annotation_endpoint_does_not_read_private_notes_without_login(self):
        with patch.object(store,'journal',side_effect=AssertionError('Private data was read')):
            result,_=fixture.Management.request(self,fixture.Management.env(self),False,'{}')
        self.assertIn('401 Unauthorized',result)

if __name__=='__main__':unittest.main()
