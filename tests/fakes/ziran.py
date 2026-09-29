"""A PATH stub for the documented trace CLI, never the installed scanner."""

import json
from pathlib import Path
import shlex
import sys


def install(tmp_path, monkeypatch, report, *, code=1, version='0.39.0', malformed=False):
    directory = tmp_path / 'scanner-bin'
    directory.mkdir(exist_ok=True)
    report_path = directory / 'report.json'
    report_path.write_text('not json' if malformed else json.dumps(report))
    script = directory / 'stub.py'
    script.write_text('''import json, sys
from pathlib import Path
base = Path(__file__).parent
args = sys.argv[1:]
with (base / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps(args) + '\\n')
if args == ['--version']:
    print('ziran, version ' + VERSION)
    raise SystemExit(0)
assert args[:3] == ['analyze-traces', '--source', 'otel']
assert args[3] == '--input' and args[5] == '--out' and args[7:] == ['--format', 'json']
source = Path(args[4])
try:
    lines = source.read_text().splitlines()
    valid = []
    for line in lines:
        try:
            valid.append(json.loads(line))
        except ValueError:
            pass
    if not valid:
        raise ValueError('no valid lines')
except (OSError, ValueError):
    raise SystemExit(2)
Path(args[6], 'trace_analysis.json').write_text((base / 'report.json').read_text())
print('scanner diagnostic only', file=sys.stderr)
raise SystemExit(CODE)
'''.replace('VERSION', repr(version)).replace('CODE', repr(code)))
    executable = directory / 'ziran'
    executable.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' '
                          + shlex.quote(str(script)) + ' "$@"\n')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(directory))
    return directory
