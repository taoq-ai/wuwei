"""Stage, inventory and sign the installable plugin archive."""

import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cli'))

from wuwei import integrity  # noqa: E402

SHIPPED = ('.claude-plugin', 'cli', 'hooks', 'charters', 'skills', 'agents', 'keys')


def build(output, key):
    stage = Path(output) / 'wuwei'
    stage.mkdir(parents=True)
    for name in SHIPPED:
        shutil.copytree(ROOT / name, stage / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (stage / 'scripts').mkdir()
    shutil.copy2(ROOT / 'scripts' / 'wuwei', stage / 'scripts' / 'wuwei')
    for name in ('README.md', 'LICENSE', 'NOTICE', 'SECURITY.md'):
        if (ROOT / name).is_file():
            shutil.copyfile(ROOT / name, stage / name)
    integrity.write_manifest(stage)
    integrity.sign(stage, key)
    problems = integrity.measure(stage)
    if problems:
        raise ValueError('; '.join(problems))
    return Path(shutil.make_archive(str(Path(output) / 'wuwei'), 'gztar', output, 'wuwei'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(build(args.output, args.key))
        return 0
    except (OSError, ValueError) as exc:
        print(f'release unmeasured: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
