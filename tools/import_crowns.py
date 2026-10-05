"""Build the public crown roster and optionally import personal Notion progress."""
import argparse
import csv
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NAMES = {'Nerscilla': 'Nerscylla', 'Kut-Ku': 'Yian Kut-Ku',
         'W. Doshaguma': 'Wächter-Doshaguma', 'W. Rathalos': 'Wächter-Rathalos',
         'W. Odogaron': 'Wächter-Vulkan-Odogaron', 'W. Fulgur': 'Wächter-Fulgur-Anjanath'}


def read_export(path):
    monsters = json.loads((ROOT / 'seed/monsters.json').read_text(encoding='utf-8'))
    from app import normalized
    by_name = {normalized(m['name']): m for m in monsters}
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.endswith('_all.csv'))
        rows = list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
    roster, progress = [], {}
    for row in rows:
        monster = by_name[normalized(NAMES.get(row['Monster'], row['Monster']))]
        roster.append({k: monster[k] for k in ('id', 'name', 'icon', 'source')})
        progress[monster['id']] = {'small': row['Small Crown'] == 'Yes', 'gold': row['Big Crown'] == 'Yes'}
    return roster, progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', type=Path)
    parser.add_argument('--build-seed', action='store_true')
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args()
    roster, progress = read_export(args.zip)
    if args.build_seed:
        (ROOT / 'seed/crowns.json').write_text(json.dumps(roster, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.data_dir:
        from app import Tracker
        tracker = Tracker(args.data_dir)
        for mid, flags in progress.items():
            tracker.set_crown_progress(mid, flags)
    print(f'{len(roster)} Monster verarbeitet.')


if __name__ == '__main__':
    main()
