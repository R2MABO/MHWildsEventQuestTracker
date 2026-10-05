import io
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
import zipfile

import catalogs
from app import Tracker, parse_package, ROOT
from test_tracker import quest, package


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.tracker = Tracker(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def record(self, kind, name):
        return next(r for r in self.tracker.state()['catalogs'][kind] if r['name'] == name)

    def create(self, kind, name, **values):
        return self.tracker.save_catalog({'kind':kind,'name':name,**values}, True)

    def test_default_icons_colors_and_neutral_state(self):
        monsters = self.tracker.state()['catalogs']['monster']
        self.assertEqual(len(monsters),36)
        self.assertTrue(all((self.tracker.images / r['icon']).is_file() for r in monsters))
        for name,color in [('Tempered','#7837FC'),('Archtempered','#BE4233'),('Frenzy','#1C0037')]:
            self.assertEqual(self.record('state',name)['color'],color)
        self.assertIsNone(self.record('state','Normal')['color'])
        self.assertTrue(self.record('state','Normal')['is_none'])

    def test_custom_state_and_monster_are_required_catalog_records(self):
        q=quest()
        q['targets'][0].update(monster='Testmonster',type='Neue Form')
        with self.assertRaises(ValueError): self.tracker.save_quest(q,True)
        monster=self.create('monster','Testmonster')
        status=self.create('state','Neue Form',color='#abcdef')
        self.tracker.save_quest(q,True)
        target=self.tracker.state()['quests'][0]['targets'][0]
        self.assertEqual(target['monster_id'],monster['id'])
        self.assertEqual(target['type_id'],status['id'])
        self.assertEqual(status['color'],'#ABCDEF')
        with self.assertRaises(ValueError): self.create('state','Fehler',color='red')
        with self.assertRaises(ValueError): self.create('monster','Test-Monster')

    def test_reward_color_persists_and_roundtrips_with_catalogs(self):
        reward=self.record('reward_type','Ausrüstung')
        self.assertIsNone(reward.get('color'))
        saved=self.tracker.save_catalog({**reward,'color':'#abcdef'})
        self.assertEqual(saved['color'],'#ABCDEF')
        reopened=Tracker(self.temp.name)
        self.assertEqual(next(r for r in reopened.state()['catalogs']['reward_type'] if r['id']==reward['id'])['color'],'#ABCDEF')
        blob=self.tracker.export()
        self.tracker.save_catalog({**saved,'color':'#112233'})
        preview=self.tracker.preview(blob)
        self.tracker.commit(preview['token'],{})
        self.assertEqual(self.record('reward_type','Ausrüstung')['color'],'#112233')
        preview=self.tracker.preview(blob)
        self.tracker.commit(preview['token'],{},update_catalogs=True)
        self.assertEqual(self.record('reward_type','Ausrüstung')['color'],'#ABCDEF')
        self.tracker.save_catalog({**saved,'color':None})
        self.assertIsNone(self.record('reward_type','Ausrüstung')['color'])

    def test_reward_color_validation_accepts_legacy_records(self):
        legacy={'id':str(uuid.uuid4()),'kind':'reward_type','name':'Alte Belohnung'}
        self.assertIsNone(catalogs.validate_record(legacy)['color'])
        custom=self.create('reward_type','Neue Belohnung',color='#123abc')
        self.assertEqual(custom['color'],'#123ABC')
        for invalid in ('red','#abc','#1234567','',123,False):
            with self.subTest(color=invalid), self.assertRaises(ValueError):
                catalogs.validate_record({**legacy,'color':invalid})

    def test_area_colors_persist_and_roundtrip(self):
        for kind in ('area',):
            with self.subTest(kind=kind):
                record = self.create(kind, 'Farbig ' + kind, color='#abcdef')
                self.assertEqual(record['color'], '#ABCDEF')
                reopened = Tracker(self.temp.name)
                actual = next(r for r in reopened.state()['catalogs'][kind] if r['id'] == record['id'])
                self.assertEqual(actual['color'], '#ABCDEF')
                blob = self.tracker.export()
                self.tracker.save_catalog({**record, 'color': '#112233'})
                preview = self.tracker.preview(blob)
                self.tracker.commit(preview['token'], {})
                self.assertEqual(self.record(kind, record['name'])['color'], '#112233')
                preview = self.tracker.preview(blob)
                self.tracker.commit(preview['token'], {}, update_catalogs=True)
                self.assertEqual(self.record(kind, record['name'])['color'], '#ABCDEF')
                self.tracker.save_catalog({**record, 'color': None})
                self.assertIsNone(self.record(kind, record['name'])['color'])

    def test_area_color_validation_accepts_legacy_records(self):
        for kind in ('area',):
            legacy = {'id': str(uuid.uuid4()), 'kind': kind, 'name': 'Alter Eintrag'}
            self.assertIsNone(catalogs.validate_record(legacy)['color'])
            for invalid in ('red', '#abc', '#1234567', '', 123, False):
                with self.subTest(kind=kind, color=invalid), self.assertRaises(ValueError):
                    catalogs.validate_record({**legacy, 'color': invalid})

    def test_rename_and_merge_preserve_quest_ids_progress_and_import_aliases(self):
        q=quest()
        self.tracker.save_quest(q,True)
        self.tracker.set_progress(q['id'],{'first_clear':True,'all_rewards':True})
        old=self.record('monster','Rey-Dau')
        renamed=self.tracker.save_catalog({**old,'name':'Rey Dau geändert'})
        self.assertEqual(renamed['id'],old['id'])
        actual=self.tracker.state()['quests'][0]
        self.assertEqual(actual['targets'][0]['monster'],'Rey Dau geändert')
        target=self.create('monster','Zielmonster')
        self.tracker.merge_catalog(old['id'],target['id'])
        actual=self.tracker.state()['quests'][0]
        self.assertEqual(actual['id'],q['id'])
        self.assertEqual(actual['targets'][0]['monster_id'],target['id'])
        self.assertTrue(actual['progress']['all_rewards'])
        preview=self.tracker.preview(package([q]))
        self.tracker.commit(preview['token'],{q['id']:'update:'+q['id']})
        self.assertEqual(self.tracker.state()['quests'][0]['targets'][0]['monster'],'Zielmonster')
        with tempfile.TemporaryDirectory() as directory:
            other=Tracker(directory)
            preview=other.preview(self.tracker.export())
            other.commit(preview['token'],{q['id']:'add'},update_catalogs=True)
            self.assertEqual(other.state()['quests'][0]['targets'][0]['monster'],'Zielmonster')

    def test_state_merge_rewrites_each_target_independently(self):
        q=quest()
        q['targets']=[{'monster':'Rey-Dau','type':'Tempered','count':1},{'monster':'Rathalos','type':'Normal','count':1}]
        self.tracker.save_quest(q,True)
        self.tracker.merge_catalog(self.record('state','Tempered')['id'],self.record('state','Frenzy')['id'])
        targets=self.tracker.state()['quests'][0]['targets']
        self.assertEqual([t['type'] for t in targets],['Frenzy','Normal'])
        with self.assertRaises(ValueError): self.tracker.merge_catalog(self.record('state','Normal')['id'],self.record('state','Frenzy')['id'])
        with self.assertRaises(ValueError): self.tracker.save_catalog({**self.record('state','Normal'),'name':'Anders'})

    def test_extra_lists_roundtrip_and_rename(self):
        area=self.create('area','Windebene')
        reward=self.create('reward_type','Spezialbelohnung')
        q=quest()
        q.update(area=area['name'],area_id=area['id'],quest_type='Jagd',reward_types=[reward['name']])
        self.tracker.save_quest(q,True)
        self.tracker.save_catalog({**area,'name':'Windebene neu'})
        actual=self.tracker.state()['quests'][0]
        self.assertEqual(actual['area'],'Windebene neu')
        blob=self.tracker.export()
        with tempfile.TemporaryDirectory() as directory:
            other=Tracker(directory)
            preview=other.preview(blob)
            other.commit(preview['token'],{q['id']:'add'})
            copied=other.state()['quests'][0]
            self.assertEqual(copied['area_id'],area['id'])
            self.assertEqual(copied['area'],actual['area'])
            self.assertEqual(copied['reward_types'],['Spezialbelohnung'])

    def test_catalog_import_preserves_local_metadata_unless_opted_in(self):
        status=self.record('state','Tempered')
        blob=self.tracker.export()
        self.tracker.save_catalog({**status,'color':'#112233'})
        preview=self.tracker.preview(blob)
        self.tracker.commit(preview['token'],{})
        self.assertEqual(self.record('state','Tempered')['color'],'#112233')
        preview=self.tracker.preview(blob)
        self.tracker.commit(preview['token'],{},update_catalogs=True)
        self.assertEqual(self.record('state','Tempered')['color'],'#7837FC')
        parsed=parse_package(blob)
        self.assertEqual(len([r for r in parsed['catalogs'] if r['kind']=='monster']),36)
        self.assertEqual(len(parsed['images']),36)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            self.assertNotIn('userdata.json',archive.namelist())

    def test_legacy_custom_tags_are_ignored_on_import_and_export(self):
        q = quest()
        tag_id, foreign_id = str(uuid.uuid4()), str(uuid.uuid4())
        q.update(tags=['Alt'], tag_ids=[tag_id])
        blob = io.BytesIO()
        with zipfile.ZipFile(blob, 'w') as archive:
            archive.writestr('catalog.json', json.dumps({
                'format': 'mh-wilds-quests', 'version': 2, 'quests': [q],
                'catalogs': [{'id': tag_id, 'kind': 'tag', 'name': 'Alt'}],
                'catalog_id_aliases': [{'foreign_id': foreign_id, 'kind': 'tag', 'target_id': tag_id}],
            }))
        preview = self.tracker.preview(blob.getvalue())
        self.tracker.commit(preview['token'], {q['id']: 'add'})
        parsed = parse_package(self.tracker.export())
        self.assertNotIn('tags', parsed['quests'][0])
        self.assertNotIn('tag_ids', parsed['quests'][0])
        self.assertFalse(any(r['kind'] == 'tag' for r in parsed['catalogs']))
        self.assertNotIn('tag', self.tracker.state()['catalogs'])
        with self.assertRaises(ValueError):
            self.create('tag', 'Neu')

    def test_v2_migration_removes_custom_tags_and_preserves_progress(self):
        q = quest()
        self.tracker.save_quest(q, True)
        self.tracker.set_progress(q['id'], {'first_clear': True, 'all_rewards': True})
        tag_id = str(uuid.uuid4())
        with self.tracker.connect() as db:
            raw = json.loads(db.execute('SELECT data FROM quests WHERE id=?', (q['id'],)).fetchone()[0])
            raw.update(tags=['Alt'], tag_ids=[tag_id])
            db.execute('UPDATE quests SET data=? WHERE id=?', (json.dumps(raw), q['id']))
            db.execute('INSERT INTO catalog_entries VALUES (?,?,?,?,?)',
                       (tag_id, 'tag', 'Alt', 'alt', json.dumps({'id': tag_id, 'kind': 'tag', 'name': 'Alt'})))
            db.execute('INSERT INTO catalog_name_aliases VALUES (?,?,?)', ('tag', 'alt', tag_id))
            db.execute('INSERT INTO catalog_id_aliases VALUES (?,?,?)', (str(uuid.uuid4()), 'tag', tag_id))
            db.execute('PRAGMA main.user_version=2')
        personal = (Path(self.temp.name) / 'userdata.sqlite').read_bytes()
        reopened = Tracker(self.temp.name)
        actual = reopened.state()['quests'][0]
        self.assertNotIn('tags', actual)
        self.assertNotIn('tag_ids', actual)
        self.assertTrue(actual['progress']['all_rewards'])
        self.assertEqual((Path(self.temp.name) / 'userdata.sqlite').read_bytes(), personal)
        with reopened.connect() as db:
            for table in ('catalog_entries', 'catalog_name_aliases', 'catalog_id_aliases'):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table} WHERE kind='tag'").fetchone()[0], 0)
        backup_path = Path(self.temp.name) / 'migration-backup-v2/quests.sqlite'
        self.assertTrue(backup_path.is_file())
        with closing(sqlite3.connect(backup_path)) as backup:
            self.assertEqual(backup.execute("SELECT COUNT(*) FROM catalog_entries WHERE kind='tag'").fetchone()[0], 1)

    def test_v1_migration_backs_up_and_preserves_personal_database(self):
        with tempfile.TemporaryDirectory() as directory:
            q=quest()
            q['targets'][0].update(monster='ReyDau',type='Rasend')
            db=sqlite3.connect(Path(directory)/'quests.sqlite')
            db.execute('CREATE TABLE quests (id TEXT PRIMARY KEY,name TEXT,data TEXT)')
            db.execute('INSERT INTO quests VALUES (?,?,?)',(q['id'],q['name'],json.dumps(q)))
            db.execute('PRAGMA user_version=1');db.commit();db.close()
            db=sqlite3.connect(Path(directory)/'userdata.sqlite')
            db.execute('CREATE TABLE progress (quest_id TEXT PRIMARY KEY,first_clear INTEGER,all_rewards INTEGER)')
            db.execute('CREATE TABLE aliases (foreign_id TEXT PRIMARY KEY,quest_id TEXT)')
            foreign=str(uuid.uuid4())
            db.execute('INSERT INTO progress VALUES (?,1,1)',(q['id'],))
            db.execute('INSERT INTO aliases VALUES (?,?)',(foreign,q['id']))
            db.execute('PRAGMA user_version=1')
            db.commit();db.close()
            tracker=Tracker(directory)
            actual=tracker.state()['quests'][0]
            self.assertEqual(actual['id'],q['id'])
            self.assertEqual(actual['targets'][0]['monster'],'Rey-Dau')
            self.assertEqual(actual['targets'][0]['type'],'Frenzy')
            self.assertTrue(actual['progress']['all_rewards'])
            # Crown storage adds a table; existing quest progress and aliases stay intact.
            with tracker.connect() as db:
                self.assertEqual(db.execute('SELECT * FROM personal.progress').fetchall(), [(q['id'], 1, 1)])
                self.assertEqual(db.execute('SELECT * FROM personal.aliases').fetchall(), [(foreign, q['id'])])
            self.assertTrue((Path(directory)/'migration-backup-v1/quests.sqlite').is_file())

    def test_identity_cannot_change_category_during_import(self):
        monster=self.record('monster','Rey-Dau')
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as archive:
            archive.writestr('catalog.json',json.dumps({'format':'mh-wilds-quests','version':2,'quests':[],'catalogs':[{'id':monster['id'],'kind':'area','name':'Falsche Kategorie'}]}))
        preview=self.tracker.preview(blob.getvalue())
        with self.assertRaises(ValueError): self.tracker.commit(preview['token'],{})
        self.assertEqual(self.record('monster','Rey-Dau')['id'],monster['id'])
        self.assertEqual(self.tracker.state()['catalogs']['area'],[])

    def test_missing_catalog_icon_rejects_preview(self):
        blob=io.BytesIO()
        with zipfile.ZipFile(blob,'w') as archive:
            archive.writestr('catalog.json',json.dumps({'format':'mh-wilds-quests','version':2,'quests':[],'catalogs':[{'id':str(uuid.uuid4()),'kind':'monster','name':'Fehlendes Icon','icon':'a'*64+'.png'}]}))
        with self.assertRaises(ValueError): self.tracker.preview(blob.getvalue())

    def test_public_seed_starts_without_personal_progress(self):
        preview=self.tracker.preview((ROOT/'seed/catalog.zip').read_bytes())
        self.tracker.commit(preview['token'],{row['quest']['id']:'add' for row in preview['rows']})
        state=self.tracker.state()
        self.assertEqual(len(state['quests']),53)
        self.assertTrue(all(not q['progress']['first_clear'] and not q['progress']['all_rewards'] for q in state['quests']))
        self.assertTrue(all((self.tracker.images/key).is_file() for q in state['quests'] for key in q['images']))


if __name__=='__main__': unittest.main()
