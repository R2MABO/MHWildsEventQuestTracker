"""Create a portable source ZIP with a public quest catalog, excluding personal data."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / name for name in ('app.py', 'README.md', '.gitignore', 'start.bat', 'start.sh', 'start.command')]
FILES += sorted((ROOT / 'web').glob('*'))
FILES += [ROOT / 'seed' / 'catalog.zip']
FILES += [ROOT / 'tests' / 'test_tracker.py', ROOT / 'tools' / 'package_release.py']


def main():
    output = ROOT / 'dist' / 'wilds-quest-tracker.zip'
    output.parent.mkdir(exist_ok=True)
    # A whitelist makes it impossible to accidentally include data/userdata.sqlite.
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in FILES:
            relative = path.relative_to(ROOT)
            entry = zipfile.ZipInfo('WildsQuestTracker/' + relative.as_posix())
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = (0o100755 if path.suffix in ('.sh', '.command') else 0o100644) << 16
            zf.writestr(entry, path.read_bytes())
    print(output)


if __name__ == '__main__':
    main()
