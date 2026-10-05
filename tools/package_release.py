"""Create a portable source ZIP and the current OS's standalone release ZIP."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'WildsQuestTracker'
PLATFORMS = {'win32': 'windows', 'linux': 'linux', 'darwin': 'macos'}
# Explicit whitelist: never bundle data/, .python-path or personal exports.
RESOURCES = ('web', 'seed/catalog.zip', 'seed/monsters.json', 'seed/crowns.json',
             'seed/icons', 'seed/ICON_SOURCES.md')
SOURCE_FILES = ('app.py', 'catalogs.py', 'README.md', 'LICENSE', '.gitignore',
                'start.bat', 'start.sh', 'start.command',
                'tools/build.bat', 'tools/build.sh', 'tools/package_release.py',
                'tools/native_launcher.py', 'tools/requirements-build.txt',
                'tools/smoke_release.py', 'tools/fetch_monsters.py',
                'tools/fetch_crown_icons.py', 'tools/import_crowns.py')


def build_source(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / 'wilds-quest-tracker.zip'
    files = [ROOT / name for name in SOURCE_FILES]
    for resource in RESOURCES:
        path = ROOT / resource
        files.extend(sorted(p for p in path.rglob('*') if p.is_file())
                     if path.is_dir() else [path])
    files.extend(sorted(path for path in (ROOT / 'tests').iterdir()
                        if path.is_file() and path.suffix in ('.py', '.js')))
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            entry = zipfile.ZipInfo(f'{NAME}/{path.relative_to(ROOT).as_posix()}')
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.suffix in ('.sh', '.command') else 0o644
            entry.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(entry, path.read_bytes())
    print(f'Quellcode-ZIP erfolgreich: {output}', flush=True)
    return output


def build_command(work: Path, target: str) -> list[str]:
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--noupx', '--name', NAME, '--paths', str(ROOT),
               '--distpath', str(work / 'dist'), '--workpath', str(work / 'build'),
               '--specpath', str(work)]
    for resource in RESOURCES:
        source = ROOT / resource
        destination = resource if source.is_dir() else Path(resource).parent.as_posix()
        command.extend(['--add-data', f'{source}:{destination}'])
    if target == 'macos':
        command.extend(['--onedir', '--windowed', '--osx-bundle-identifier',
                        'org.wildsquesttracker.app'])
    else:
        command.append('--onefile')
    if target == 'windows':
        command.extend(['--icon', str(ROOT / 'web/favicon.ico')])
    command.append(str(ROOT / 'tools/native_launcher.py'))
    return command


def write_zip(folder: Path, output: Path) -> None:
    """Preserve Unix executable bits for the standalone Linux executable."""
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                entry = zipfile.ZipInfo(path.relative_to(folder.parent).as_posix())
                entry.create_system = 3
                entry.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644
                entry.external_attr = (stat.S_IFREG | mode) << 16
                archive.writestr(entry, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    parser.add_argument('--source-only', action='store_true',
                        help='Nur die plattformübergreifende Quellcode-ZIP erstellen (ohne PyInstaller)')
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    build_source(output_dir)
    if args.source_only:
        return 0
    target = PLATFORMS.get(sys.platform)
    if target is None:
        parser.error(f'Nicht unterstütztes Betriebssystem: {sys.platform}')
    if importlib.util.find_spec('PyInstaller') is None:
        parser.error('Build-Abhängigkeit fehlt: python -m pip install -r tools/requirements-build.txt')
    for resource in RESOURCES:
        if not (ROOT / resource).exists():
            parser.error(f'Öffentliche Build-Ressource fehlt: {resource}')
    output = output_dir / f'wilds-quest-tracker-{target}.zip'
    # All staging is fresh, so an old build or a local data/ folder cannot leak in.
    with tempfile.TemporaryDirectory(prefix='wilds-build-') as temporary:
        work = Path(temporary)
        subprocess.run(build_command(work, target), cwd=ROOT, check=True)
        folder = work / 'release' / NAME
        folder.mkdir(parents=True)
        if target == 'macos':
            shutil.copytree(work / 'dist' / f'{NAME}.app', folder / f'{NAME}.app', symlinks=True)
        else:
            executable = NAME + ('.exe' if target == 'windows' else '')
            shutil.copy2(work / 'dist' / executable, folder / executable)
        for name in ('README.md', 'LICENSE'):
            shutil.copy2(ROOT / name, folder / name)
        (folder / 'BUILD.txt').write_text(
            f'OS: {target}\nArchitecture: {platform.machine()}\nPython: {platform.python_version()}\n',
            encoding='utf-8')
        staged_zip = work / output.name
        if target == 'macos':
            # ditto preserves .app symlinks and bundle metadata for Finder extraction.
            subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                            str(folder), str(staged_zip)], check=True)
        else:
            write_zip(folder, staged_zip)
        shutil.copy2(staged_zip, output)
    print(f'Build erfolgreich: {output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
