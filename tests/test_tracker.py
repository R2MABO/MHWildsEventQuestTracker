from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid
import zipfile
from http.server import ThreadingHTTPServer

from app import Tracker, ValidationError, image_key, make_handler, parse_package

PNG = b'\x89PNG\r\n\x1a\n' + b'fixture'


def quest(name='Eine Jagd', qid=None):
    return {'id': qid or str(uuid.uuid4()), 'name': name, 'targets': [{'monster': 'Rey-Dau', 'type': 'Archtempered', 'count': 1}],
            'rank': 'High-Rank', 'hr': 50, 'stars': 8, 'reward_types': ['Ausrüstung', 'Materialien'],
            'rewards': [{'name': 'Zertifikat γ', 'required': '13+'}], 'images': [], 'notes': ''}


def package(quests, images=None, private=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.writestr('catalog.json', json.dumps({'format': 'mh-wilds-quests', 'version': 1, 'quests': quests}))
        for key, blob in (images or {}).items():
            zf.writestr('images/' + key, blob)
        if private is not None:
            zf.writestr('userdata.json', json.dumps(private))
    return buffer.getvalue()


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.tracker = Tracker(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def add(self, q=None):
        q = q or quest()
        self.tracker.save_quest(q, True)
        return q

    def test_catalog_export_never_contains_progress_or_aliases(self):
        q = self.add()
        self.tracker.set_progress(q['id'], {'first_clear': True, 'all_rewards': True})
        with self.tracker.connect() as db:
            db.execute('INSERT INTO personal.aliases VALUES (?,?)', (str(uuid.uuid4()), q['id']))
        with zipfile.ZipFile(io.BytesIO(self.tracker.export())) as zf:
            self.assertEqual(zf.namelist(), ['catalog.json'])
            raw = json.loads(zf.read('catalog.json'))
        self.assertNotIn('progress', raw['quests'][0])
        self.assertNotIn('first_clear', json.dumps(raw))
        with closing(sqlite3.connect(Path(self.temporary.name) / 'quests.sqlite')) as db:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(names, {'quests'})

    def test_completion_invariant(self):
        q = self.add()
        result = self.tracker.set_progress(q['id'], {'first_clear': False, 'all_rewards': True})
        self.assertTrue(result['first_clear'])
        self.assertTrue(result['all_rewards'])

    def test_same_id_update_preserves_progress_and_id(self):
        q = self.add()
        self.tracker.set_progress(q['id'], {'first_clear': True, 'all_rewards': False})
        q['name'] = 'Anderer Questname'
        preview = self.tracker.preview(package([q]))
        self.assertTrue(preview['rows'][0]['exact'])
        self.tracker.commit(preview['token'], {q['id']: preview['rows'][0]['default']})
        actual = self.tracker.state()['quests'][0]
        self.assertEqual(actual['name'], 'Anderer Questname')
        self.assertEqual(actual['id'], q['id'])
        self.assertTrue(actual['progress']['first_clear'])

    def test_independent_duplicate_requires_confirmation_and_remembers_alias(self):
        local = self.add()
        incoming = quest()
        preview = self.tracker.preview(package([incoming]))
        self.assertFalse(preview['rows'][0]['exact'])
        self.assertEqual(preview['rows'][0]['default'], 'skip')
        self.assertEqual(preview['rows'][0]['candidates'][0]['id'], local['id'])
        self.tracker.commit(preview['token'], {incoming['id']: 'update:' + local['id']})
        incoming['name'] = 'Völlig umbenannt'
        next_preview = self.tracker.preview(package([incoming]))
        self.assertTrue(next_preview['rows'][0]['exact'])
        self.assertEqual(next_preview['rows'][0]['default'], 'update:' + local['id'])
        self.assertEqual(len(self.tracker.state()['quests']), 1)

    def test_import_keeps_unmentioned_local_quests(self):
        local = self.add()
        incoming = quest('Neue Jagd')
        preview = self.tracker.preview(package([incoming]))
        self.tracker.commit(preview['token'], {incoming['id']: 'add'})
        self.assertEqual({q['id'] for q in self.tracker.state()['quests']}, {local['id'], incoming['id']})

    def test_explicit_separate_copy_uses_new_id(self):
        q = self.add()
        preview = self.tracker.preview(package([q]))
        self.tracker.commit(preview['token'], {q['id']: 'add'})
        rows = self.tracker.state()['quests']
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['id'] for r in rows}), 2)

    def test_invalid_multiple_assignments_roll_back_entire_import(self):
        local = self.add()
        a, b = quest(), quest('Andere')
        preview = self.tracker.preview(package([a, b]))
        with self.assertRaises(ValidationError):
            self.tracker.commit(preview['token'], {a['id']: 'update:' + local['id'], b['id']: 'update:' + local['id']})
        self.assertEqual(self.tracker.state()['quests'][0]['name'], local['name'])
        self.assertEqual(len(self.tracker.state()['quests']), 1)

    def test_private_backup_progress_is_opt_in(self):
        q = self.add()
        self.tracker.set_progress(q['id'], {'first_clear': True, 'all_rewards': True})
        blob = self.tracker.export(True)
        self.tracker.set_progress(q['id'], {'first_clear': False, 'all_rewards': False})
        preview = self.tracker.preview(blob)
        self.assertTrue(preview['has_progress'])
        self.tracker.commit(preview['token'], {q['id']: 'update:' + q['id']})
        self.assertFalse(self.tracker.state()['quests'][0]['progress']['all_rewards'])
        preview = self.tracker.preview(blob)
        self.tracker.commit(preview['token'], {q['id']: 'update:' + q['id']}, True)
        self.assertTrue(self.tracker.state()['quests'][0]['progress']['all_rewards'])

    def test_full_backup_restores_images_and_aliases_in_new_directory(self):
        q = quest()
        q['images'] = [self.tracker.save_image(PNG)]
        self.add(q)
        incoming = quest()
        preview = self.tracker.preview(package([incoming]))
        self.tracker.commit(preview['token'], {incoming['id']: 'update:' + q['id']})
        # Attach the image again after the incoming quest replaced its metadata.
        self.tracker.save_quest(q)
        self.tracker.set_progress(q['id'], {'first_clear': True, 'all_rewards': True})
        with tempfile.TemporaryDirectory() as directory:
            other = Tracker(directory)
            preview = other.preview(self.tracker.export(True))
            other.commit(preview['token'], {q['id']: 'add'}, True)
            self.assertEqual((other.images / q['images'][0]).read_bytes(), PNG)
            self.assertTrue(other.state()['quests'][0]['progress']['all_rewards'])
            self.assertTrue(other.preview(package([incoming]))['rows'][0]['exact'])

    def test_invalid_archives_and_missing_images_are_rejected_without_change(self):
        q = quest()
        q['images'] = [image_key(PNG)]
        with self.assertRaises(ValidationError):
            self.tracker.preview(package([q]))
        with self.assertRaises(ValidationError):
            self.tracker.preview(b'not zip')
        with self.assertRaises(ValidationError):
            self.tracker.preview(package([q, q], {image_key(PNG): PNG}))
        self.assertEqual(self.tracker.state()['quests'], [])

    def test_unsafe_zip_path_rejected(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as zf:
            zf.writestr('../outside.txt', 'unsafe')
        with self.assertRaises(ValidationError):
            self.tracker.preview(output.getvalue())

    def test_future_stars_multiple_monsters_and_freetext_survive_roundtrip(self):
        q = quest()
        q['stars'] = 15
        q['rank'] = 'Master-Rank'
        q['targets'].append({'monster': 'Neues Monster', 'type': 'Rasend', 'count': 4})
        q['rewards'].append({'name': 'Anhänger', 'required': '7x für jeden Anhänger'})
        self.add(q)
        parsed = parse_package(self.tracker.export())
        self.assertEqual(parsed['quests'][0], q)

    def test_invalid_quest_never_written(self):
        q = quest()
        q['stars'] = -1
        with self.assertRaises(ValidationError):
            self.add(q)
        self.assertEqual(self.tracker.state()['quests'], [])

    def test_delete_removes_progress_and_aliases(self):
        q = self.add()
        self.tracker.set_progress(q['id'], {'first_clear': True, 'all_rewards': True})
        foreign = quest()
        preview = self.tracker.preview(package([foreign]))
        self.tracker.commit(preview['token'], {foreign['id']: 'update:' + q['id']})
        self.tracker.delete_quest(q['id'])
        with self.tracker.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM personal.progress').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM personal.aliases').fetchone()[0], 0)

    def test_notion_mappings_counts_freetext_and_personal_separation(self):
        csv_data = 'Questname,1. Abschluss,Alle Belohnungen erhalten,Belohnung,Belohnungsart,Benötigte Anzahl,Bilder,JR,Jagdziel,Sterne\nTest,No,Yes,Ticket,Ausrüstung,13+,,100+,3 §Gravios + !Nerscylla + []Rey-Dau + $Gypceros,10\n'
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as zf:
            zf.writestr('Eventquests_all.csv', csv_data.encode('utf-8'))
        parsed = parse_package(output.getvalue())
        q = parsed['quests'][0]
        self.assertEqual([t['type'] for t in q['targets']], ['Tempered', 'Rasend', 'Archtempered', 'Tempered'])
        self.assertEqual(q['targets'][0]['count'], 3)
        self.assertEqual(q['rewards'][0]['required'], '13+')
        self.assertNotIn('progress', q)
        self.assertTrue(parsed['progress'][q['id']]['first_clear'])

    def test_deleting_all_quests_does_not_mark_catalog_as_new(self):
        q = self.add()
        self.tracker.delete_quest(q['id'])
        reopened = Tracker(self.temporary.name)
        self.assertFalse(reopened.new_catalog)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.tracker = Tracker(cls.temporary.name)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(cls.tracker, 'test-token'))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temporary.cleanup()

    def test_session_and_host_validation(self):
        raw = json.dumps(quest()).encode()
        with self.assertRaises(HTTPError) as result:
            urlopen(Request(self.url + '/api/quest/create', raw, {'Content-Type': 'application/json'}))
        self.assertEqual(result.exception.code, 403)
        with self.assertRaises(HTTPError) as result:
            urlopen(Request(self.url + '/api/state', headers={'Host': 'evil.invalid'}))
        self.assertEqual(result.exception.code, 403)

    def test_http_create_progress_export_and_no_traversal(self):
        raw = json.dumps(quest()).encode()
        with urlopen(Request(self.url + '/api/quest/create', raw, {'X-Tracker-Token': 'test-token', 'Content-Type': 'application/json'})) as response:
            created = json.load(response)
        with urlopen(self.url + '/api/state') as response:
            self.assertTrue(any(q['id'] == created['id'] for q in json.load(response)['quests']))
        with urlopen(self.url + '/') as response:
            html = response.read()
            self.assertIn(b'test-token', html)
            self.assertNotIn(b'__TRACKER_TOKEN__', html)
        with self.assertRaises(HTTPError) as result:
            urlopen(self.url + '/images/../../app.py')
        self.assertEqual(result.exception.code, 404)

    def test_download_route_returns_public_zip_with_attachment_header(self):
        with urlopen(self.url + '/api/export/catalog') as response:
            self.assertEqual(response.headers['Content-Type'], 'application/zip')
            self.assertIn('wilds-questliste.zip', response.headers['Content-Disposition'])
            exported = parse_package(response.read())
        self.assertEqual(exported['progress'], {})
        self.assertEqual(exported['aliases'], {})


if __name__ == '__main__':
    unittest.main()
