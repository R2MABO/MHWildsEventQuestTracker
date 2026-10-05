"""Entry point for native releases, including logs for the macOS GUI bundle."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import traceback

import app


def main():
    macos_bundle = getattr(sys, 'frozen', False) and sys.platform == 'darwin'
    if not macos_bundle and sys.stdout is not None and sys.stderr is not None:
        return app.main()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--data-dir', type=Path, default=app.default_data_directory())
    args, _ = parser.parse_known_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    with (args.data_dir / 'tracker-start.log').open('a', encoding='utf-8', buffering=1) as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                return app.main()
            except Exception:
                traceback.print_exc()
                return 1


if __name__ == '__main__':
    raise SystemExit(main())
