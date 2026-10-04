"""Download the user-requested MHWilds wiki monster icons into local seed assets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
import uuid
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://monsterhunterwiki.org'
CATEGORY = BASE + '/wiki/Category:MHWilds_Monster_Icons'
LARGE = {
    'Ajarakan': 'Ajarakan', 'Alpha_Doshaguma': 'Alpha-Doshaguma', 'Arkveld': 'Arkveld',
    'Balahara': 'Balahara', 'Blangonga': 'Blangonga', 'Chatacabra': 'Chatacabra',
    'Congalala': 'Congalala', 'Doshaguma': 'Doshaguma', 'Gogmazios': 'Gogmazios',
    'Gore_Magala': 'Gore Magala', 'Gravios': 'Gravios', 'Guardian_Arkveld': 'Wächter-Arkveld',
    'Guardian_Doshaguma': 'Wächter-Doshaguma', 'Guardian_Ebony_Odogaron': 'Wächter-Vulkan-Odogaron',
    'Guardian_Fulgur_Anjanath': 'Wächter-Fulgur-Anjanath', 'Guardian_Rathalos': 'Wächter-Rathalos',
    'Gypceros': 'Gypceros', 'Hirabami': 'Hirabami', 'Jin_Dahaad': 'Jin-Dahaad', 'Lagiacrus': 'Lagiacrus',
    'Lala_Barina': 'Lala-Barina', 'Mizutsune': 'Mizutsune', 'Nerscylla': 'Nerscylla', 'Nu_Udra': 'Nu-Udra',
    'Omega_Planetes': 'Omega Planetes', 'Quematrice': 'Quematrice', 'Rathalos': 'Rathalos', 'Rathian': 'Rathian',
    'Rey_Dau': 'Rey-Dau', 'Rompopolo': 'Rompopolo', 'Seregios': 'Seregios', 'Uth_Duna': 'Uth-Duna',
    'Xu_Wu': 'Xu-Wu', 'Yian_Kut-Ku': 'Yian Kut-Ku', 'Zoh_Shia': 'Zoh Shia', 'Question_Mark': 'Unbekannt',
}
ALIASES = {'Mizutsune': ['Misutsune'], 'Unbekannt': ['?????'],
           'Wächter-Arkveld': ['W.-Arkveld'], 'Wächter-Doshaguma': ['W.-Doshaguma'],
           'Wächter-Vulkan-Odogaron': ['W.-Vulkan-Odogaron'],
           'Wächter-Fulgur-Anjanath': ['W.-Fulgur-Anjanath'], 'Wächter-Rathalos': ['W.-Rathalos']}
NAMESPACE = uuid.UUID('1dbb9727-3381-4b04-bda2-7a458e5ab748')


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'WildsQuestTracker/1.0 (personal offline catalog)'}), timeout=30) as response:
        return response.read()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs)
        if tag == 'img':
            self.images.append(attrs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    output = ROOT / '.test-artifacts' / 'wiki'
    output.mkdir(parents=True, exist_ok=True)
    html = fetch(CATEGORY).decode('utf-8')
    (output / 'category.html').write_text(html, encoding='utf-8')
    links = Links()
    links.feed(html)
    files = {link['href']: link.get('title', '') for link in links.links if '/wiki/File:' in link['href']}
    print(json.dumps(files, ensure_ascii=False, indent=2))
    print('Images:', json.dumps(links.images[:3], ensure_ascii=False))
    print('API:', [link['href'] for link in links.links if 'api' in link['href'].lower()])
    if args.inspect:
        return
    icons_dir = ROOT / 'seed' / 'icons'
    icons_dir.mkdir(parents=True, exist_ok=True)
    records = []

    def download(item):
        stem, name = item
        match = next((img['src'] for img in links.images if '/MHWA-' + stem + '_Icon.' in img.get('src', '')), None)
        if not match:
            raise RuntimeError('Kein Icon für ' + name)
        prefix = match.split('/thumb/', 1)[1].rsplit('/', 1)[0]
        url = BASE + '/images/' + prefix
        blob = fetch(url)
        ext = '.png' if blob.startswith(b'\x89PNG\r\n\x1a\n') else '.webp' if blob[:4] == b'RIFF' and blob[8:12] == b'WEBP' else None
        if not ext:
            raise RuntimeError('Ungültiges Icon für ' + name)
        key = hashlib.sha256(blob).hexdigest() + ext
        (icons_dir / key).write_bytes(blob)
        file_url = next(urljoin(BASE, href) for href in files if 'MHWA-' + stem + '_Icon.' in href)
        return {'id': str(uuid.uuid5(NAMESPACE, 'monster:' + stem)), 'kind': 'monster', 'name': name,
                'icon': key, 'aliases': ALIASES.get(name, []), 'source': file_url}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for record in pool.map(download, LARGE.items()):
            records.append(record)
            print('Gespeichert:', record['name'], flush=True)
    (ROOT / 'seed' / 'monsters.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'seed' / 'ICON_SOURCES.md').write_text('# Monster-Icons\n\nQuelle: ' + CATEGORY + '\n\nDie Spielgrafiken gehören Capcom. Lokal heruntergeladene Wiki-Dateien für diesen Fan-Tracker.\n\n' + '\n'.join('- [' + r['name'] + '](' + r['source'] + ')' for r in records), encoding='utf-8')
    print('Fertig:', len(records) - 1, 'große Monster/Varianten und ein Unbekannt-Icon.')


if __name__ == '__main__':
    main()
