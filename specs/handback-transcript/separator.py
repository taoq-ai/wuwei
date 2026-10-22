"""Build the line-separator sentinel fixtures in tests/fixtures/transcripts from a real Claude Code session, redacted.

Usage: python3 -I specs/handback-transcript/separator.py <session>.jsonl <agent>.jsonl <agent>.meta.json <out dir>

The seat is a security gate whose transcript holds a raw U+2028 inside a JSON string (a probe class it wrote into
its verdict). JSON allows that character unescaped and the harness writes it so; str.splitlines() splits on it.
Kept: the brief (replaced), the last Write row that holds U+2028 and its result, the hand-back row and its result,
with their keys, ids, uuids, parent links, timestamps and usage, and the session's launch rows. Replaced: the brief,
the Write input (by a short verdict line around the real separator), the hand-back message (by a report naming a
security verdict for I-1) and local paths. Rows are read split on newlines only and written with the character raw.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hook-transcript'))
from fixtures import launch, redact  # noqa: E402

REPORT = ('Security gate on acme/app#42 at aaaaaaa: PASS.\n\nVerdict file: .wuwei/verdicts/I-1/security-aaaaaaa.md\n\n'
          'Confidence: high\nBlocked: none\nGap: none\nChange: none')


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').split('\n') if line.strip()]


def seat(found):
    """The brief, the Write that holds U+2028 and its result, the hand-back and its result."""
    names = lambda r, name: [p for p in (r.get('message') or {}).get('content') or () if isinstance(p, dict) and p.get('name') == name]  # noqa: E731
    end = max(i for i, r in enumerate(found) if names(r, 'SubagentHandback'))
    wrote = max(i for i, r in enumerate(found[:end]) if names(r, 'Write') and ' ' in json.dumps(r, ensure_ascii=False))
    kept = [found[0], found[wrote], found[wrote + 1], found[end], found[end + 1]]
    kept[0]['message']['content'] = 'Item: I-1\nGate it.'
    for part in names(kept[1], 'Write'):
        text = part['input']['content']
        at = text.index(' ')
        part['input'] = {'file_path': '/repo/.wuwei/verdicts/I-1/security-aaaaaaa.md', 'content': text[text.rfind('(', 0, at):text.find(')', at) + 1]}
        kept[1]['wireToolInputs'] = {part['id']: part['input']}
    kept[2]['toolUseResult'] = {}
    for part in kept[2]['message']['content']:
        part['content'] = 'File created successfully at: /repo/.wuwei/verdicts/I-1/security-aaaaaaa.md'
    for part in names(kept[3], 'SubagentHandback'):
        part['input'] = {'message': REPORT}
        kept[3]['wireToolInputs'] = {part['id']: part['input']}
    for row in kept:
        row.pop('serverClassifierContext', None)  # the machine's git state: not part of the flow
    return kept


def main(session, agent, meta, out):
    home, out = str(Path.home()), Path(out)
    found = rows(session)
    cwd = next(r['cwd'] for r in found if r.get('cwd'))
    use = json.loads(Path(meta).read_text(encoding='utf-8'))['toolUseId']
    started = [launch(redact(r, home, cwd)) for r in found if use in json.dumps(r) and r.get('type') in ('assistant', 'user')
               and '<task-notification>' not in json.dumps(r)]  # not its notifications, which hold the real report
    for row in started:
        row.pop('serverClassifierContext', None)
    (out / 'sentinel-separator-launch.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in started), encoding='utf-8')
    mine = seat([redact(r, home, cwd) for r in rows(agent)])
    (out / Path(agent).name).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in mine), encoding='utf-8')
    (out / Path(meta).name).write_text(Path(meta).read_text(encoding='utf-8'), encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:])
