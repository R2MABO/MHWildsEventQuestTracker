"""Download the two crown UI icons from the requested wiki category."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://monsterhunterwiki.org/wiki/Category:MHWiki_Monster_UI_Icons'


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img':
            for kind, filename in [('small', 'MHWI-Small_Crown.png'), ('gold', 'MHWI-Gold_Crown.png')]:
                src = attrs.get('src', '')
                if '/' + filename + '/' in src:
                    self.urls[kind] = src.split('/thumb/')[0] + '/' + src.split('/thumb/')[1].rsplit('/', 1)[0]


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'WildsQuestTracker/1.0 (personal offline tracker)'}), timeout=30) as response:
        return response.read()


def main():
    parser = Images()
    parser.feed(fetch(SOURCE).decode('utf-8'))
    for kind in ('small', 'gold'):
        blob = fetch(parser.urls[kind])
        if not blob.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Ungültiges Kronenbild')
        (ROOT / 'web' / f'crown-{kind}.png').write_bytes(blob)
        print(kind, parser.urls[kind])


if __name__ == '__main__':
    main()
