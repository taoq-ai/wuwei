"""Mutants for config-door, one at a time, applied to both copies of the file (cli/wuwei/ and the vendored .claude/wuwei/cli/wuwei/)
in a copy of the tree. A mutant names guards.py unless its fourth field names another file.

    python3 -I mutants.py <tree copy> [pytest args...]

A mutant is killed when pytest fails a test (exit 1); a collection or usage error (exit 2 or more) is reported as such.
"""
import subprocess
import sys
from pathlib import Path

MUTANTS = [
    ('OWNED without plan.json', "('config.toml', 'plan.json')  # below", "('config.toml',)  # below"),
    ('OWNED without config.toml', "('config.toml', 'plan.json')  # below", "('plan.json',)  # below"),
    ('bash own empty', 'own, text = OWNED * seat,', 'own, text = (),'),
    ('redirect target without own', 'any(records(t, CACHE + own) for t in targets)', 'any(records(t, CACHE) for t in targets)'),
    ('writer argument without own', "(LEDGER if program == 'rm' else CACHE) + own)", "(LEDGER if program == 'rm' else CACHE))"),
    ('rm without own', "(LEDGER if program == 'rm' else CACHE) + own)", "(LEDGER if program == 'rm' else CACHE + own))"),
    ('edit without OWNED', 'records(p, CACHE + OWNED * seat)', 'records(p, CACHE)'),
    ('no seat door words', 'DOOR_WORDS + SEAT_WORDS * seat if', 'DOOR_WORDS if'),
    ('seat path word gone', r"SEAT_WORDS = ((r'\.wuwei[/.]*/(config|plan)\b',), ", 'SEAT_WORDS = ('),
    ('seat path word without config', r"SEAT_WORDS = ((r'\.wuwei[/.]*/(config|plan)\b',), ", r"SEAT_WORDS = ((r'\.wuwei[/.]*/(plan)\b',), "),
    ('seat cli word gone', r""", (r'(wuwei(\.__main__)?|executable[)`]?)[\'"]?(\s|\\\n)+(--\s+)?[$\'"]*(config|plan|sync)\b',))""", ',)'),
    ('seat cli word without $', r"""(--\s+)?[$\'"]*(config|plan|sync)""", r"""(--\s+)?[\'"]?(config|plan|sync)"""),
    ('seat cli word without --', r"""(\s|\\\n)+(--\s+)?[$""", r"""(\s|\\\n)+[$"""),
    ('seat cli word without executable', r"""(r'(wuwei(\.__main__)?|executable[)`]?)[""", r"""(r'(wuwei(\.__main__)?)["""),
    ('seat cli word without sync', r"""[$\'"]*(config|plan|sync)\b',))""", r"""[$\'"]*(config|plan)\b',))"""),
    ('seat text quoted only', "command + ' ' + unquoted(command) * seat", 'command'),
    ('unquote keeps quotes', """re.sub('\\\\$?[\\'"]', '', text)))""", 'text))'),
    ('unquote keeps $ before a quote', """re.sub('\\\\$?[\\'"]', '', text)))""", """re.sub('[\\'"]', '', text)))"""),
    ('unquote keeps backslashes', "return re.sub(r'\\\\', '', re.sub(r'\\\\(x", "return (lambda t: t)(re.sub(r'\\\\(x"),
    ('unquote decodes nothing', "lambda e: chr(min(int(", "lambda e: e[0] or chr(min(int("),
    ('unquote without octal', '|U[0-9a-fA-F]{1,8}|[0-7]{1,3})', '|U[0-9a-fA-F]{1,8})'),
    ('unquote without \\u', '{1,2}|u[0-9a-fA-F]{1,4}|U', '{1,2}|U'),
    ('eval not read', "(progname(argv[0]) == 'eval' or progname(argv[0]) in SHELLS", "(progname(argv[0]) in SHELLS"),
    ('eval body first word only', "segments(' '.join(argv[body:]) if progname(argv[0]) == 'eval' else argv[body]", 'segments(argv[body]'),
    ('eval not a program a wrapper finds', "'find', 'eval'} | SHELLS", "'find'} | SHELLS"),
    ('builtin not a wrapper', "'command', 'builtin', 'exec'", "'command', 'exec'"),
    ('no depth bound', '    if depth > 64:', '    if False:'),
    ('mcp push without the seat state check', "if seat and branch == 'wuwei/state' else", "if False else"),
    ('unquote without \\U', '|U[0-9a-fA-F]{1,8}|[0-7]', '|[0-7]'),
    ('depth not passed down', "else argv[body], depth + 1)", "else argv[body], depth)"),
    ('depth not passed to unwrap', '_unwrap(current, depth) if current', '_unwrap(current) if current'),
    ('too deep not refused', 'except RecursionError:  # eval in eval', 'except ZeroDivisionError:  # eval in eval'),
    ('no SEAT_CLI check', 'if seat and re.search(SEAT_CLI,', 'if False and re.search(SEAT_CLI,'),
    ('SEAT_CLI without bare segment', "SEAT_CLI = r'(^|(^wuwei", "SEAT_CLI = r'((^wuwei"),
    ('SEAT_CLI without executable', '(^wuwei|executable[)`]?|', '(^wuwei|'),
    ('SEAT_CLI executable without backtick', '(^wuwei|executable[)`]?|', '(^wuwei|executable[)]?|'),
    ('SEAT_CLI without -m', r"|\0-[^\0-]*m\0?(runpy\0)?(cli\.)?wuwei(\.__main__)?)\0)(--\0)?(config", r")\0)(--\0)?(config"),
    ('SEAT_CLI without --', r")\0)(--\0)?(config", r")\0)(config"),
    ('SEAT_CLI without config', r'(config\0|sync', r'(sync'),
    ('SEAT_CLI without sync', r'(config\0|sync(\0|$)|plan', r'(config\0|plan'),
    ('SEAT_CLI action first only', r'plan\0([\s\S]*\0)?(add', r'plan\0(add'),
    ('SEAT_CLI without session', 'restore|run|session|tier', 'restore|run|tier'),
    ('SEAT_CLI without tier', 'session|tier|approve', 'session|approve'),
    ('SEAT_CLI action prefix', r'tier|approve)(\0|$))', r'tier|approve))'),
    ('state branch open', "*['wuwei/state'] * seat]", '*[] * seat]'),
    ('state branch shut for all', "*['wuwei/state'] * seat]", "*['wuwei/state'] * True]"),
    ('state push names the default branch', "OWNER_ONLY.strip() if hit[0] == 'wuwei/state' else", "'' if hit[0] == 'wuwei/state' else"),
    ('git push drops seat', 'git_push(root, rest[i + 1:], here, seat)', 'git_push(root, rest[i + 1:], here)'),
    ('sed -i literal again', "any(re.match('-[^-]*[iI]|--i', a) for a in argv)", "'-i' in argv"),
    ('sed without --i', "re.match('-[^-]*[iI]|--i', a)", "re.match('-[^-]*[iI]', a)"),
    ('sed cluster first only', "re.match('-[^-]*[iI]|--i', a)", "re.match('-[iI]|--i', a)"),
    ('sed without -I', "re.match('-[^-]*[iI]|--i', a)", "re.match('-[^-]*i|--i', a)"),
    ('ledger deny without owner line', 'return deny(LEDGER_DENIED + OWNER_ONLY * seat)\n        if any(harness',
     'return deny(LEDGER_DENIED)\n        if any(harness'),
    ('edit deny without owner line', 'return deny(LEDGER_DENIED + OWNER_ONLY * seat) if any(records(p,', 'return deny(LEDGER_DENIED) if any(records(p,'),
    ('unreadable without owner line', "Write tool.' + OWNER_ONLY * any(", "Write tool.' + '' * any("),
    ('every session a seat', "seat = payload.get('cwd') or '.', bool(payload.get('agent_type'))", "seat = payload.get('cwd') or '.', True"),
    ('no session a seat', "seat = payload.get('cwd') or '.', bool(payload.get('agent_type'))", "seat = payload.get('cwd') or '.', False"),
    ('bash call drops seat', "payload.get('session_id', ''), seat)", "payload.get('session_id', ''))"),
    ('hook error path without seat words', "guards.DOOR_WORDS + guards.SEAT_WORDS * bool(payload.get('agent_type'))", 'guards.DOOR_WORDS', 'hook.py'),
    ('hook error path seat words for all', "guards.SEAT_WORDS * bool(payload.get('agent_type'))", 'guards.SEAT_WORDS', 'hook.py'),
]

tree, args = Path(sys.argv[1]).resolve(), sys.argv[2:] or ['tests/test_guards.py']
for name, old, new, *where in MUTANTS:
    copies = [tree / 'cli' / 'wuwei' / (where or ['guards.py'])[0], tree / '.claude' / 'wuwei' / 'cli' / 'wuwei' / (where or ['guards.py'])[0]]
    originals = [p.read_text(encoding='utf-8') for p in copies]
    assert originals[0] == originals[1] and originals[0].count(old) == 1, (name, originals[0].count(old))
    for path, text in zip(copies, originals):
        path.write_text(text.replace(old, new), encoding='utf-8')
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', *args], cwd=tree, capture_output=True, text=True)
    failed = next((line.split(' ')[1] for line in run.stdout.splitlines() if line.startswith('FAILED ')), '')
    verdict = {0: 'SURVIVED', 1: 'killed'}.get(run.returncode, f'error {run.returncode}')
    print(f'{verdict:<9} {name}: {failed}', flush=True)
    for path, text in zip(copies, originals):
        path.write_text(text, encoding='utf-8')
