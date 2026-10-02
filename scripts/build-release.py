"""Stage, inventory and sign the installable plugin archive."""

import argparse
from pathlib import Path
import shutil

from wuwei import integrity


def build(source, output, key):
    source, output = Path(source), Path(output)
    stage = output / 'wuwei'
    stage.mkdir(parents=True)
    for name in ('.claude-plugin', 'cli', 'adapters', 'bin', 'hooks', 'charters',
                 'skills', 'agents', 'templates', 'keys', 'docs'):
        shutil.copytree(source / name, stage / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'LICENSE', 'NOTICE', 'SECURITY.md', 'pyproject.toml'):
        shutil.copyfile(source / name, stage / name)
    integrity.write_manifest(stage)
    result = integrity.signature_adapter().sign(stage / integrity.MANIFEST, key)
    if result.exit:
        raise OSError(result.reason)
    result = integrity.measure(stage)
    if result.exit:
        raise ValueError(result.reason)
    return Path(shutil.make_archive(str(output / 'wuwei'), 'gztar', output, 'wuwei'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(build(Path(__file__).resolve().parents[1], args.output, args.key))
        return 0
    except (OSError, ValueError) as exc:
        print(f'release unmeasured: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
