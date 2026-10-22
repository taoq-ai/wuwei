"""Build the sentinel fixtures in tests/fixtures/transcripts from a real Claude Code session, redacted.

Usage: python3 -I specs/handback-transcript/fixtures.py <session>.jsonl <agent>.jsonl <agent>.meta.json <out dir>

The seat is a gate that ended with SubagentHandback. Kept: its first row (the brief, replaced), the hand-back
tool_use row and its tool_result row, with their keys, ids, uuids, parent links, timestamps and usage; the meta
file as the harness wrote it; and the session's launch rows (its notification, which holds the real report, is
left out). Replaced: the brief, the hand-back message (by a report that names an arch verdict for I-1) and local
paths, as specs/hook-transcript/fixtures.py does.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hook-transcript'))
from fixtures import launch, redact  # noqa: E402

REPORT = ('Arch gate on acme/app#42 at aaaaaaa: PASS.\n\nVerdict file: .wuwei/verdicts/I-1/arch-aaaaaaa.md\n\n'
          'Confidence: high\nBlocked: none\nGap: none\nChange: none')


def seat(rows):
    """The brief, the hand-back and its result: the rows the hook reads, with the brief and the report replaced."""
    end = max(i for i, r in enumerate(rows) if any(isinstance(p, dict) and p.get('name') == 'SubagentHandback'
                                                   for p in (r.get('message') or {}).get('content') or ()))
    kept = [rows[0], rows[end], rows[end + 1]]
    kept[0]['message']['content'] = 'Item: I-1\nGate it.'
    for part in kept[1]['message']['content']:
        part['input'] = {'message': REPORT}
        kept[1]['wireToolInputs'] = {part['id']: part['input']}
    for row in kept:
        row.pop('serverClassifierContext', None)  # the machine's git state: not part of the flow
    return kept


def main(session, agent, meta, out):
    home, out = str(Path.home()), Path(out)
    rows = [json.loads(line) for line in Path(session).read_text(encoding='utf-8').splitlines()]
    cwd = next(r['cwd'] for r in rows if r.get('cwd'))
    use = json.loads(Path(meta).read_text(encoding='utf-8'))['toolUseId']
    found = [launch(redact(r, home, cwd)) for r in rows if use in json.dumps(r) and r.get('type') in ('assistant', 'user')]  # not its notification
    for row in found:
        row.pop('serverClassifierContext', None)
    (out / 'sentinel-launch.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in found), encoding='utf-8')
    mine = seat([redact(json.loads(line), home, cwd) for line in Path(agent).read_text(encoding='utf-8').splitlines()])
    (out / Path(agent).name).write_text(''.join(json.dumps(r) + '\n' for r in mine), encoding='utf-8')
    (out / Path(meta).name).write_text(Path(meta).read_text(encoding='utf-8'), encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:])
