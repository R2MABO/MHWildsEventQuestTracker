"""Start a release from its extracted ZIP, with no installed Python required by it."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile


@contextmanager
def running(executable, cwd, port, log):
    process = subprocess.Popen([str(executable), '--no-browser', '--auto-stop', '--port', str(port)],
                               cwd=cwd, stdout=log, stderr=log)
    session = None
    try:
        deadline = time.monotonic() + 60
        url = f'http://127.0.0.1:{port}'
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Release exited with code {process.returncode}')
            try:
                with urlopen(url + '/api/health', timeout=1) as response:
                    health = json.load(response)
            except OSError:
                time.sleep(.2)
                continue
            if health.get('ok'):
                session = urlopen(url + '/api/session?token=' + health['token'], timeout=5)
                session.readline()
                yield url, health['token']
                return
        raise RuntimeError('Release did not start within 60 seconds')
    finally:
        if session is not None:
            session.close()
        try:
            process.wait(timeout=20 if session is not None else 1)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            raise RuntimeError('Release did not exit automatically after disconnect')


def read_json(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='wilds-smoke-') as temporary:
        root = Path(temporary)
        if sys.platform == 'darwin':
            subprocess.run(['ditto', '-x', '-k', str(args.archive.resolve()), str(root)], check=True)
        else:
            with zipfile.ZipFile(args.archive) as archive:
                assert not any('/data/' in name or name.endswith(('.bat', '.sh', '.command'))
                               for name in archive.namelist())
                archive.extractall(root)
                for entry in archive.infolist():
                    mode = (entry.external_attr >> 16) & 0o777
                    if mode:
                        (root / entry.filename).chmod(mode)
        folder = root / 'WildsQuestTracker'
        executable = folder / ('WildsQuestTracker.exe' if sys.platform == 'win32' else 'WildsQuestTracker')
        if sys.platform == 'darwin':
            executable = folder / 'WildsQuestTracker.app/Contents/MacOS/WildsQuestTracker'
        # An unrelated working directory catches accidental cwd-relative resource/data paths.
        cwd = root / 'unrelated'
        cwd.mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with (root / 'smoke.log').open('w', encoding='utf-8') as log:
            try:
                with running(executable, cwd, port, log) as (url, token):
                    state = read_json(url + '/api/state')
                    assert state['quests'], 'Public quest seed missing'
                    assert not any(q['progress']['first_clear'] or q['progress']['all_rewards']
                                   for q in state['quests']), 'Personal quest progress leaked'
                    assert len(state['crowns']) == 29, 'Public crown seed missing'
                    assert not any(m['small'] or m['gold'] for m in state['crowns']), 'Personal crowns leaked'
                    for path in ('/', '/app.js', '/style.css', '/favicon.ico', '/crown-gold.png',
                                 '/images/' + state['crowns'][0]['icon']):
                        with urlopen(url + path, timeout=5) as response:
                            assert response.status == 200 and response.read(), path
                    monster_id = state['crowns'][0]['id']
                    request = Request(url + '/api/crowns/progress',
                                      json.dumps({'id': monster_id, 'progress': {'small': True, 'gold': False}}).encode(),
                                      {'Content-Type': 'application/json', 'X-Tracker-Token': token})
                    with urlopen(request, timeout=5) as response:
                        assert response.status == 200
                assert (folder / 'data/userdata.sqlite').is_file(), 'User data not next to executable'
                assert not (cwd / 'data').exists(), 'User data depends on working directory'
                with running(executable, cwd, port, log) as (url, _):
                    crowns = read_json(url + '/api/state')['crowns']
                    assert next(m for m in crowns if m['id'] == monster_id)['small'], 'Progress lost after restart'
            except Exception:
                log.flush()
                print((root / 'smoke.log').read_text(encoding='utf-8'), file=sys.stderr)
                app_log = folder / 'data/tracker-start.log'
                if app_log.exists():
                    print(app_log.read_text(encoding='utf-8'), file=sys.stderr)
                raise
    print('Native ZIP verified: resources, clean seed, portable data and restart persistence.')


if __name__ == '__main__':
    main()
