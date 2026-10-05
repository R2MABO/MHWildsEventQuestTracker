from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import app
from tools import package_release
from tools import native_launcher


class ReleaseTests(unittest.TestCase):
    def test_source_only_contains_all_starters_and_no_personal_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(package_release.sys, 'argv',
                              ['package_release.py', '--source-only', '--output-dir', temporary]), \
                    patch.object(package_release.importlib.util, 'find_spec',
                                 side_effect=AssertionError('Source build must not need PyInstaller')):
                self.assertEqual(package_release.main(), 0)
            with zipfile.ZipFile(Path(temporary) / 'wilds-quest-tracker.zip') as archive:
                names = set(archive.namelist())
                for name in ('start.bat', 'start.sh', 'start.command', 'app.py', 'catalogs.py',
                             'web/index.html', 'seed/catalog.zip', 'tools/package_release.py'):
                    self.assertIn('WildsQuestTracker/' + name, names)
                    self.assertEqual(archive.read('WildsQuestTracker/' + name),
                                     (package_release.ROOT / name).read_bytes())
                self.assertFalse(any('/data/' in name or '.python-path' in name
                                     or '__pycache__' in name or 'userdata.sqlite' in name for name in names))
                for name in ('start.sh', 'start.command', 'tools/build.sh'):
                    mode = archive.getinfo('WildsQuestTracker/' + name).external_attr >> 16
                    self.assertEqual(mode & 0o777, 0o755)

    def test_macos_launcher_logs_even_when_stdout_exists(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            def start():
                print('Native startup')
                return 0
            with patch.object(native_launcher.sys, 'frozen', True, create=True), \
                    patch.object(native_launcher.sys, 'platform', 'darwin'), \
                    patch.object(native_launcher.sys, 'argv', ['WildsQuestTracker']), \
                    patch.object(app, 'default_data_directory', return_value=folder), \
                    patch.object(app, 'main', side_effect=start):
                self.assertEqual(native_launcher.main(), 0)
            self.assertIn('Native startup', (folder / 'tracker-start.log').read_text(encoding='utf-8'))

    def test_source_data_directory(self):
        with patch.object(app.sys, 'frozen', False, create=True):
            self.assertEqual(app.default_data_directory(), app.ROOT / 'data')

    def test_native_data_is_beside_executable_not_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            with patch.object(app.sys, 'frozen', True, create=True), \
                    patch.object(app.sys, 'executable', str(folder / 'WildsQuestTracker.exe')), \
                    patch.object(app.sys, 'platform', 'win32'), \
                    patch.object(app, 'ROOT', folder / '_MEI123'):
                self.assertEqual(app.default_data_directory(), folder / 'data')

    def test_macos_data_is_outside_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            binary = folder / 'WildsQuestTracker.app/Contents/MacOS/WildsQuestTracker'
            with patch.object(app.sys, 'frozen', True, create=True), \
                    patch.object(app.sys, 'executable', str(binary)), \
                    patch.object(app.sys, 'platform', 'darwin'):
                self.assertEqual(app.default_data_directory(), folder / 'data')

    def test_zip_preserves_executable_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'WildsQuestTracker'
            folder.mkdir()
            binary = folder / 'WildsQuestTracker'
            binary.write_bytes(b'public binary')
            binary.chmod(0o755)
            (folder / 'LICENSE').write_text('license', encoding='utf-8')
            # Sibling personal data must not be included when zipping the staging folder.
            (folder.parent / 'userdata.sqlite').write_bytes(b'private')
            output = folder.parent / 'release.zip'
            package_release.write_zip(folder, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {'WildsQuestTracker/WildsQuestTracker', 'WildsQuestTracker/LICENSE'})
                mode = archive.getinfo('WildsQuestTracker/WildsQuestTracker').external_attr >> 16
                self.assertEqual(bool(mode & stat.S_IXUSR), bool(binary.stat().st_mode & stat.S_IXUSR))

    def test_build_only_bundles_public_resources(self):
        for target in ('windows', 'linux', 'macos'):
            command = package_release.build_command(Path('build'), target)
            resources = [command[i + 1] for i, value in enumerate(command) if value == '--add-data']
            self.assertEqual(len(resources), len(package_release.RESOURCES))
            self.assertFalse(any('userdata' in resource or '.python-path' in resource for resource in resources))
            self.assertIn('--windowed' if target == 'macos' else '--onefile', command)


if __name__ == '__main__':
    unittest.main()
