import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile

from app import ROOT, Tracker, ValidationError, parse_package


class CrownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.tracker = Tracker(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_roster_and_no_private_seed_progress(self):
        expected = json.loads((ROOT / 'seed/crowns.json').read_text(encoding='utf-8'))
        monsters = self.tracker.state()['crowns']
        self.assertEqual(len(monsters), 29)
        self.assertEqual([m['id'] for m in monsters], [m['id'] for m in expected])
        self.assertFalse(any(m['small'] or m['gold'] for m in monsters))
        self.assertTrue(all((self.tracker.images / m['icon']).is_file() for m in monsters))
        self.assertNotIn('Zoh Shia', [m['name'] for m in monsters])

    def test_progress_and_order_survive_reopen_and_invalid_order_is_atomic(self):
        monsters = self.tracker.state()['crowns']
        mid = monsters[0]['id']
        self.tracker.set_crown_progress(mid, {'small': False, 'gold': True})
        ids = [m['id'] for m in reversed(monsters)]
        self.tracker.reorder_crowns(ids)
        reopened = Tracker(self.temp.name)
        actual = reopened.state()['crowns']
        self.assertEqual([m['id'] for m in actual], ids)
        self.assertTrue(actual[-1]['gold'])
        self.assertFalse(actual[-1]['small'])
        for invalid in [ids[:-1], ids[:-1] + [ids[0]], ids + [str(uuid.uuid4())], 'bad']:
            with self.assertRaises(ValidationError):
                reopened.reorder_crowns(invalid)
            self.assertEqual([m['id'] for m in reopened.state()['crowns']], ids)
        for flags in [{'small': 1, 'gold': False}, {}, {'small': False, 'gold': 'yes'}]:
            with self.assertRaises(ValidationError):
                reopened.set_crown_progress(mid, flags)
        with self.assertRaises(ValidationError):
            reopened.set_crown_progress(str(uuid.uuid4()), {'small': True, 'gold': True})

    def test_create_edit_and_image_validation(self):
        image = self.tracker.save_image(b'\x89PNG\r\n\x1a\nfixture')
        monster = self.tracker.save_crown_monster({'name': 'Testmonster', 'icon': image}, True)
        self.tracker.set_crown_progress(monster['id'], {'small': True, 'gold': False})
        self.tracker.save_crown_monster({**monster, 'name': 'Neues Testmonster'})
        actual = Tracker(self.temp.name).state()['crowns'][-1]
        self.assertEqual(actual['name'], 'Neues Testmonster')
        self.assertEqual(actual['icon'], image)
        self.assertTrue(actual['small'])
        with self.assertRaises(ValidationError):
            self.tracker.save_crown_monster({'name': 'Neues-Testmonster', 'icon': None}, True)
        for name, icon in [('', None), ('Fehlt', '0' * 64 + '.png'), ('Unsicher', '../image.png')]:
            with self.assertRaises(ValidationError):
                self.tracker.save_crown_monster({'name': name, 'icon': icon}, True)

    def test_private_backup_restores_custom_monsters_flags_and_order_only_on_opt_in(self):
        image = self.tracker.save_image(b'\x89PNG\r\n\x1a\ncustom')
        custom = self.tracker.save_crown_monster({'name': 'Backupmonster', 'icon': image}, True)
        self.tracker.set_crown_progress(custom['id'], {'small': True, 'gold': True})
        ids = [m['id'] for m in reversed(self.tracker.state()['crowns'])]
        self.tracker.reorder_crowns(ids)
        backup = self.tracker.export(True)
        with tempfile.TemporaryDirectory() as directory:
            other = Tracker(directory)
            preview = other.preview(backup)
            self.assertTrue(preview['has_progress'])
            self.assertEqual(preview['crown_count'], 30)
            other.commit(preview['token'], {}, restore_progress=False)
            self.assertEqual(len(other.state()['crowns']), 29)
            preview = other.preview(backup)
            other.commit(preview['token'], {}, restore_progress=True)
            actual = Tracker(directory).state()['crowns']
            self.assertEqual([m['id'] for m in actual], ids)
            self.assertTrue(actual[0]['small'] and actual[0]['gold'])
            self.assertEqual((other.images / image).read_bytes(), b'\x89PNG\r\n\x1a\ncustom')
        with zipfile.ZipFile(io.BytesIO(self.tracker.export())) as archive:
            self.assertNotIn('userdata.json', archive.namelist())
            self.assertNotIn(f'images/{image}', archive.namelist())

    def test_backup_rejects_duplicate_ids_and_wrong_image_hash(self):
        source = self.tracker.export(True)
        for mutation in ['duplicate', 'image']:
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(output, 'w') as archive:
                private = json.loads(original.read('userdata.json'))
                if mutation == 'duplicate':
                    private['crowns'].append(private['crowns'][0])
                icon = private['crowns'][0]['icon']
                for name in original.namelist():
                    content = original.read(name)
                    if name == 'userdata.json':
                        content = json.dumps(private).encode()
                    elif mutation == 'image' and name == f'images/{icon}':
                        content = b'\x89PNG\r\n\x1a\nwrong'
                    archive.writestr(name, content)
            with self.assertRaises(ValidationError):
                parse_package(output.getvalue())


if __name__ == '__main__':
    unittest.main()
