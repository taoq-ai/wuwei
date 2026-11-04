"""Mutants for config-door, one at a time, applied to both cli/wuwei/guards.py and its vendored copy in a copy of the tree.

    python3 -I mutants.py <tree copy> [pytest args...]

A mutant is killed when pytest fails a test (exit 1); a collection or usage error (exit 2 or more) is reported as such.
"""
import subprocess
import sys
from pathlib import Path

MUTANTS = [
    ('OWNED without plan.json', "('config.toml', 'plan.json')  # below", "('config.toml',)  # below"),
    ('OWNED without config.toml', "('config.toml', 'plan.json')  # below", "('plan.json',)  # below"),
    ('bash own empty', 'parts, own = segments(command), OWNED * seat', 'parts, own = segments(command), ()'),
    ('redirect target without own', 'any(records(t, CACHE + own) for t in targets)', 'any(records(t, CACHE) for t in targets)'),
    ('writer argument without own', "(LEDGER if program == 'rm' else CACHE) + own)", "(LEDGER if program == 'rm' else CACHE))"),
    ('rm without own', "(LEDGER if program == 'rm' else CACHE) + own)", "(LEDGER if program == 'rm' else CACHE + own))"),
    ('edit without OWNED', 'records(p, CACHE + OWNED * seat)', 'records(p, CACHE)'),
    ('no seat door words', 'DOOR_WORDS + SEAT_WORDS * seat if', 'DOOR_WORDS if'),
    ('seat path word gone', r"SEAT_WORDS = ((r'\.wuwei[/.]*/(config|plan)\b',), ", 'SEAT_WORDS = ('),
    ('seat cli word gone', r""", (r'\bwuwei(\.__main__)?[\'"]?(\s|\\\n)+[$\'"]*(config|plan)\b',))""", ',)'),
    ('seat cli word without $', r"""(\s|\\\n)+[$\'"]*(config|plan)""", r"""(\s|\\\n)+[\'"]?(config|plan)"""),
    ('no SEAT_CLI check', 'if seat and re.search(SEAT_CLI,', 'if False and re.search(SEAT_CLI,'),
    ('SEAT_CLI without bare segment', "SEAT_CLI = r'(^|(^wuwei", "SEAT_CLI = r'((^wuwei"),
    ('SEAT_CLI without executable', '(^wuwei|executable[)`]?|', '(^wuwei|'),
    ('SEAT_CLI executable without backtick', 'executable[)`]?', 'executable[)]?'),
    ('SEAT_CLI without -m', r"|\0-[^\0-]*m\0?(runpy\0)?(cli\.)?wuwei(\.__main__)?)\0)(--\0)?(config", r")\0)(--\0)?(config"),
    ('SEAT_CLI without --', r")\0)(--\0)?(config", r")\0)(config"),
    ('SEAT_CLI without config', r'(config\0|plan\0', r'(plan\0'),
    ('SEAT_CLI action first only', r'plan\0([\s\S]*\0)?(add', r'plan\0(add'),
    ('SEAT_CLI without session', 'restore|run|session|tier', 'restore|run|tier'),
    ('SEAT_CLI without tier', 'session|tier|approve', 'session|approve'),
    ('SEAT_CLI action prefix', r'tier|approve)(\0|$))', r'tier|approve))'),
    ('sed -i literal again', "any(re.match('-[^-]*i|--i', a) for a in argv)", "'-i' in argv"),
    ('sed without --i', "re.match('-[^-]*i|--i', a)", "re.match('-[^-]*i', a)"),
    ('sed cluster first only', "re.match('-[^-]*i|--i', a)", "re.match('-i|--i', a)"),
    ('ledger deny without owner line', 'return deny(LEDGER_DENIED + OWNER_ONLY * seat)\n        if any(harness',
     'return deny(LEDGER_DENIED)\n        if any(harness'),
    ('edit deny without owner line', 'return deny(LEDGER_DENIED + OWNER_ONLY * seat) if any(records(p,', 'return deny(LEDGER_DENIED) if any(records(p,'),
    ('unreadable without owner line', "Write tool.' + OWNER_ONLY * any(", "Write tool.' + '' * any("),
    ('every session a seat', "seat = payload.get('cwd') or '.', bool(payload.get('agent_type'))", "seat = payload.get('cwd') or '.', True"),
    ('no session a seat', "seat = payload.get('cwd') or '.', bool(payload.get('agent_type'))", "seat = payload.get('cwd') or '.', False"),
    ('bash call drops seat', "payload.get('session_id', ''), seat)", "payload.get('session_id', ''))"),
]

tree, args = Path(sys.argv[1]).resolve(), sys.argv[2:] or ['tests/test_guards.py']
copies = [tree / 'cli' / 'wuwei' / 'guards.py', tree / '.claude' / 'wuwei' / 'cli' / 'wuwei' / 'guards.py']
originals = [p.read_text(encoding='utf-8') for p in copies]
assert originals[0] == originals[1]
for name, old, new in MUTANTS:
    assert originals[0].count(old) == 1, (name, originals[0].count(old))
    for path, text in zip(copies, originals):
        path.write_text(text.replace(old, new), encoding='utf-8')
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', *args], cwd=tree, capture_output=True, text=True)
    failed = next((line.split(' ')[1] for line in run.stdout.splitlines() if line.startswith('FAILED ')), '')
    verdict = {0: 'SURVIVED', 1: 'killed'}.get(run.returncode, f'error {run.returncode}')
    print(f'{verdict:<9} {name}: {failed}', flush=True)
    for path, text in zip(copies, originals):
        path.write_text(text, encoding='utf-8')
